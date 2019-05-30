#!/usr/bin/python

import config		#Login/pw info
import os
import requests 	#To save URLs to images
from datetime import datetime, timedelta

#Email related modules
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage


dir_path = os.path.dirname(os.path.realpath(__file__))
#Setup download folder
download_dir = dir_path + '/downloads/'


#-----------------------------------------------------------------------
#Send basic email with given parameters
#-----------------------------------------------------------------------
def sendEmail(send_to, email_subject, email_body, attachment=None, images=None):
	#Logo file name/path
	file_name = "headerLogobw.png"
	file_path = dir_path + "/static/img/" + file_name

	#Msg headers
	msg = MIMEMultipart('alternative')
	msg['From'] = config.EMAIL_FROM
	msg['To'] = send_to
	msg['Subject'] = email_subject

	#Add any images (that come from the email blast)
	if images:
		for attr, value in images.__dict__.items():
			if str(attr[:6]) == 'chart_':
				img = open(download_dir + value, 'rb').read()
				msgImg = MIMEImage(img, 'png')
				msgImg.add_header('Content-ID', '<'+value+'>')
				msgImg.add_header('Content-Disposition', 'inline', filename=value)
				msg.attach(msgImg)
				email_body += ('<br><img src="cid:%s" width="700px"><br>' % value)
	
	#Add signature
	email_body += ('<br><br><br>Keep on tracking!<br><br>'
					'<i>Thanks,<br>'
					'<b>The Exercise Tracker Team</b></i><br><br>'
					'<img src="cid:headerLogo" width="175px"></body></html>')
	
	#Attach text to email body	
	msg.attach(MIMEText(email_body,'html'))
	
	#Attach Header logo for signature
	img = open(file_path, 'rb').read()
	msgImg = MIMEImage(img, 'png')
	msgImg.add_header('Content-ID', '<headerLogo>')
	msgImg.add_header('Content-Disposition', 'inline', filename="image1")
	msg.attach(msgImg)
	
	#CSV Attachment
	if attachment:
		attachment = download_dir + attachment
		csv = MIMEApplication(open(attachment).read())
		csv.add_header('Content-Disposition','attachment; filename="%s"' % os.path.basename(attachment))
		msg.attach(csv)
	
	# Sending the mail  
	server = smtplib.SMTP('smtp.gmail.com:587')
	server.starttls()
	server.login(config.EMAIL_FROM, config.EMAIL_PSWD)
	server.sendmail(config.EMAIL_FROM, send_to, msg.as_string())
	server.quit()
	

	
#-----------------------------------------------------------------------
#Log function for email_blast
#-----------------------------------------------------------------------
def log():		
	#timestamp log
	now = datetime.now()
	f=open(dir_path + '/emailblast_log.txt', "a+")
	f.write(now.strftime("%A, %B %d %Y %I:%M:%S %p\n"))
	f.close() 
	
	

#-----------------------------------------------------------------------
#Function to send email blast for given userIDs (via 'rows' variable)
#-----------------------------------------------------------------------
def makeEmail(rows, db, schedule):
	#Loop through all users
	for r in rows:

		#Create empty object to pass chart URLs to email
		class images(object):
			pass
					
		#Get user details
		query = ('SELECT email, user_name '
				'FROM user_data '
				'WHERE id = :userid')
		
		user_record = db.query(query, userid=r.user_id).first()
		user_email = user_record.email
		
		#Flag to send email or not
		makeEmail = False
		
		#Activity History - Bar Graphs
		
		#Image Chart example/explanation of URL parts
		#https://image-charts.com/chart? 				#Base URL
		#cht=bvg 										#chart type: bar chart
		#&chf=bg,s,EFEFEF								#chart fill: bg = background, s = solid, EFEFEF = color
		#&chd=t:3,2,4|5,5,5 							#dataset: 'actual,actual,actual|goal,goal,goal'
		#&chs=700x400 									#chart size
		#&chxt=x,y										#display x and y axis labels
		#chxl=0:label1|label2							#displays custom labels for axis markers
		#&chds=0,10 									#axis scale/range (only supports y axis)
		#&chco=08FF00,00D1FF 							#data set colors: 'set1,set2'
		#&chdl=Recorded+Distance|Goal+Distance 			#Legend titles: 'set1|set2'
		#&chdlp=b										#legend position, b = bottom
		#&chts=000000,20								#Chart title font options: color,size,r
		#&chtt=Biking:+Distance+vs+Goal|Last+30+Days 	#Chart title: + for space, | for line break
		
		URL_PART1 = 'https://image-charts.com/chart?cht=bvg&chd=a:'
			#next insert data ('actual,actual,actual|goal,goal,goal')
		URL_PART2 = '&chs=700x300&chf=bg,s,EFEFEF&chxt=x,y&chxl=0:'
			#next insert axis labels ('label1|label2|label3')
		URL_PART3 = '&chds=0,'
			#next insert max axis number
		URL_PART4 = '&chco='
			#next insert the two data set colors ('000000,000000')
		URL_PART5 = '&chdl=Actual+Distance|Goal+Distance&chdlp=b&chts=000000,20&chtt='
			#last insert chart title ('Chart+Title+Here')
		
		
		#Grab last x days of data
		x = r.length
		end_day = datetime.today() - timedelta(days=1)
		start_day = end_day - timedelta(days=x)
		
		#Set chart title history length
		if x == 1:
			history = 'Daily'
		elif x == 7:
			history = 'Last+7+days'
		else:
			history = 'Last+30+days'
			
		
		#Get all user's activities with goals for the last 30 days
		query = """SELECT a.time_created, 
					a.activity_type,
					a.distance as activity_distance, 
					g.distance as goal_distance
					FROM activities as a
					INNER JOIN goals as g ON a.goal_id = g.id
					WHERE a.user_id=:userID
					AND DATE(a.time_created) >= DATE(:startDay) 
					AND DATE(a.time_created) <= DATE(:endDay);"""
					
		user_activity = db.query(query, userID=r.user_id, startDay=start_day,endDay=end_day)
		
		#Start creating strings for chart URLs
		if not len(user_activity.as_dict()) == 0:
			#Set up variables
			actBike = goalBike = actRun = goalRun = actSwim = goalSwim = labelsBike = labelsRun = labelsSwim = ""
			maxDistBike = maxDistRun = maxDistSwim = 0
			
			for ua in user_activity:
				#Check the activity
				if ua.activity_type == 'Biking':
					actBike += (',%.2f' % (ua.activity_distance))
					goalBike += (',%.2f' % (ua.goal_distance))
					labelsBike += ('|'+str(datetime.date(ua.time_created)))
					
					#Set maximum distance for axis scaling
					if round(ua.activity_distance) > maxDistBike:
						maxDistBike = round(ua.activity_distance)
					if round(ua.goal_distance) > maxDistBike:
						maxDistBike = round(ua.goal_distance)
				
				elif ua.activity_type == 'Running':
					actRun += (',%.2f' % (ua.activity_distance))
					goalRun += (',%.2f' % (ua.goal_distance))
					labelsRun += ('|'+str(datetime.date(ua.time_created)))
				
					#Set maximum distance for axis scaling
					if round(ua.activity_distance) > maxDistRun:
						maxDistRun = round(ua.activity_distance)
					if round(ua.goal_distance) > maxDistRun:
						maxDistRun = round(ua.goal_distance)
				
				elif ua.activity_type == 'Swimming':
					actSwim += (',%.2f' % (ua.activity_distance))
					goalSwim += (',%.2f' % (ua.goal_distance)) 
					labelsSwim += ('|'+str(datetime.date(ua.time_created)))
				
					#Set maximum distance for axis scaling
					if round(ua.activity_distance) > maxDistSwim:
						maxDistSwim = round(ua.activity_distance)
					if round(ua.goal_distance) > maxDistSwim:
						maxDistSwim = round(ua.goal_distance)
				
			
			
			#Compile final URL Strings as needed
			if maxDistBike > 0:
				final_url = (URL_PART1 + actBike[1:] + '|' + goalBike[1:] + URL_PART2 + labelsBike + URL_PART3 + str(maxDistBike+3) + URL_PART4 + 'FCA1A1,A1BBFC' + URL_PART5 + 'Biking:+Distance+vs+Goal|' + history)
				img_data = requests.get(final_url).content
				with open(download_dir + 'bike.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_bike = 'bike.jpg'
				makeEmail = True
			
			if maxDistRun > 0:
				final_url = (URL_PART1 + actRun[1:] + '|' + goalRun[1:] + URL_PART2 + labelsRun + URL_PART3 + str(maxDistRun+3) + URL_PART4 + 'FFFD6C,FFCE6C' + URL_PART5 + 'Running:+Distance+vs+Goal|' + history)
				img_data = requests.get(final_url).content
				with open(download_dir + 'run.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_run = 'run.jpg'
				makeEmail = True
			
			if maxDistSwim > 0:
				final_url = (URL_PART1 + actSwim[1:] + '|' + goalSwim[1:] + URL_PART2 + labelsSwim + URL_PART3 + str(maxDistSwim+3) + URL_PART4 + 'A1E3FC,DFA1FC' + URL_PART5 + 'Swimming:+Distance+vs+Goal|' + history)
				img_data = requests.get(final_url).content
				with open(download_dir + 'swim.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_swim = 'swim.jpg'
				makeEmail = True




		#Health History - Line Charts
		
		#Image Chart example/explanation of URL parts
		#https://image-charts.com/chart?				#Base URL
		#cht=lc											#Chart type: line chart
		#&chf=bg,s,EFEFEF								#chart fill: bg = background, s = solid, EFEFEF = color
		#&chs=700x300									#Chart size
		#&chd=a:175,160,155,153							#Chart data
		#&chxt=x,y										#display x and y axis labels
		#&chxl=0:|label1|label2|Label3|Label4			#display custom labels for axis markers
		#&chxr=1,100,180								#axis scale/range
		#&chco=00FF00									#chart line color
		#&chts=000000,20								#chart title font options
		#&chtt=Weight|Last+30+Days						#chart title


		
		URL_PART1 = 'https://image-charts.com/chart?cht=lc&chd=a:'
			#next insert data ('data,data,data')
		URL_PART2 = '&chs=700x300&chf=bg,s,EFEFEF&chxt=x,y&chxl=0:'
			#next insert axis labels ('label1|label2|label3')
		URL_PART3 = '&chxr=1,'
			#next insert min & max axis number ('min,max')
		URL_PART4 = '&chco='
			#next insert the data set color ('000000')
		URL_PART5 = '&chts=000000,20&chtt='
			#last insert chart title ('Chart+Title+Here')
		
		
		#Get all user's health entries for the last x days
		query = """SELECT weight, bmi, time_created 
					FROM health 
					WHERE user_id=:userID 
					AND DATE(time_created) >= DATE(:startDay) 
					AND DATE(time_created) <= DATE(:endDay);"""
					
		user_health = db.query(query, userID=r.user_id, startDay=start_day,endDay=end_day)
		
		#Start creating strings for chart URLs
		if not len(user_health.as_dict()) == 0:
			#Set up variables
			weight = bmi = axisLabels = ""
			maxWeight = minWeight = maxBMI = minBMI = 0
			
			for ua in user_health:
				weight += (',%.2f' % (ua.weight))
				bmi += (',%.2f' % (ua.bmi))
				axisLabels += ('|'+str(datetime.date(ua.time_created)))
			
				#Set minimum/maximums for axis scaling
				if round(ua.weight) > maxWeight:
					maxWeight = round(ua.weight)
				if round(ua.bmi) > maxBMI:
					maxBMI = round(ua.bmi)
				if round(ua.weight) < minWeight or minWeight == 0:
					minWeight = round(ua.weight)
				if round(ua.bmi) < minBMI or minBMI == 0:
					minBMI = round(ua.bmi)	
				
			
			#Compile final URL Strings as needed
			if maxWeight > 0:
				final_url = (URL_PART1 + weight[1:] + URL_PART2 + axisLabels + URL_PART3 + str(minWeight-2) + ',' + str(maxWeight+2) + URL_PART4 + '0000FF' + URL_PART5 + 'Weight|' + history)
				img_data = requests.get(final_url).content
				with open(download_dir + 'weight.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_weight = 'weight.jpg'
				makeEmail = True
			
			if maxBMI > 0:
				final_url = (URL_PART1 + bmi[1:] + URL_PART2 + axisLabels + URL_PART3 + str(minBMI-2) + ',' + str(maxBMI+2) + URL_PART4 + 'FF0000' + URL_PART5 + 'BMI|' + history)
				img_data = requests.get(final_url).content
				with open(download_dir + 'bmi.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_bmi = 'bmi.jpg'
				makeEmail = True
			

		#Send Email
		if makeEmail == True:
		
			#Email body intro
			body_text = ('<html><body><h3>Hello %s,</h3><br>'
					'<p>Here is your %s Exercise Tracker Summary.</p>' % (user_record.user_name, schedule))
			
			#Subject line
			subject_line = ('%s Exercise Tracker Summary' % (schedule))
					
			sendEmail(user_email,subject_line,body_text,None,images)
			
			
