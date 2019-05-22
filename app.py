#!/usr/bin/env python
from flask import Flask, render_template, redirect, request, url_for, send_from_directory, flash, session
from flask_bcrypt import Bcrypt
import records
import config #config file
import sys
import string
import os
import requests
from datetime import datetime, timedelta

#email related items
import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage

#email subscription related items
import time
import atexit
from apscheduler.schedulers.background import BackgroundScheduler



app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = config.SECRET_KEY





#-----------------------------------------------------------------------
#Setup database connection
#-----------------------------------------------------------------------
def connectDB():
	return records.Database('postgres://{user}:{pw}@{url}/{dbName}'.format(user=config.POSTGRES_USER, pw=config.POSTGRES_PW, url=config.POSTGRES_URL, dbName=config.POSTGRES_DB))


#-----------------------------------------------------------------------
#Home page
#-----------------------------------------------------------------------
@app.route('/')
def index():
	if 'username' in session:
		return redirect(url_for('dashboard'))

	return render_template('index.html')
	
	
	

#-----------------------------------------------------------------------
#Login
#help from: http://flask.pocoo.org/docs/1.0/quickstart/#accessing-request-data
#-----------------------------------------------------------------------
@app.route('/login', methods=['GET','POST'])
def login():
	if request.method == 'POST':
		if valid_login(request.form['username'],request.form['password']):
			session['username'] = request.form['username']
			return redirect(url_for('dashboard'))
		else:
			flash('Invalid username or password.', 'is-error')

	# the code below is executed if the request method
	# was GET or the credentials were invalid
	return render_template('index.html')


#-----------------------------------------------------------------------
#Validate user login
#-----------------------------------------------------------------------
def valid_login(username, password):
    #Check username
	db = connectDB()
	query = ('SELECT id, user_name, pswd, user_role '
				 'FROM user_data '
				 'WHERE user_name = :user_name')
	
	user_record = db.query(query, user_name=username).first()
	
	if user_record.user_role == 'user':
		#check password
		if bcrypt.check_password_hash(user_record.pswd, password):
			return 1 #user and password validated
		else:
			return 0 #invalid password
		
	else:
		#user doesn't exist or is not defined as 'user'
		return 0


#-----------------------------------------------------------------------
#Logout
#help from: https://www.tutorialspoint.com/flask/flask_sessions.htm
#-----------------------------------------------------------------------
@app.route('/logout', methods=['GET','POST'])
def logout():
	#Remove the username from the session if it is there
	session.pop('username', None)
	return redirect(url_for('index'))

#-----------------------------------------------------------------------
#Register
#-----------------------------------------------------------------------
@app.route('/registration', methods=['GET','POST'])
def registration():
	if request.method == 'POST':
		if registration_complete(request):
			
			#Registration confirmation email
			confirmRegistration(request)
			
			flash(('Your account has been created! Please log in '
			   'with your credentials to continue.'), 'success')
			return redirect(url_for('index'))
		else:
			flash('This username or email is already taken.', 'is-error')

	# the code below is executed if the request method
	# was GET or the credentials were invalid
	return render_template('registration.html')



#-----------------------------------------------------------------------
#Register the user
#-----------------------------------------------------------------------
def registration_complete(request):
	pw_hash = bcrypt.generate_password_hash(request.form['password']).decode('utf-8')
	db = connectDB()
					 
	query = """SELECT COUNT(*) user_count
		FROM user_data
		WHERE user_name = :username OR email = :email"""

	user_count = db.query(query, username=request.form['username'],
		email=request.form['email']).first().user_count

	if user_count > 0:
		return 0
		
	else:
		#Insert main user data into 'user_data' table
		query = """INSERT INTO user_data (user_name, fname, lname, email, pswd,
			 user_role, city, state) VALUES
			 (:username, :fname, :lname, :email, :pwhash,
			 :user_role, :city, :state)"""

		db.query(query, username=request.form['username'],
			fname=request.form['firstName'], 
			lname=request.form['lastName'],
			email=request.form['email'],
			user_role='user',
			city=request.form['city'], 
			state=request.form['state'],
			pwhash=pw_hash)


		#Enter health data into the 'health' table if provided
		if request.form['heightFeet'] or request.form['heightIn'] or request.form['weight']:
			#height feet
			if request.form['heightFeet']:
				hFeet = request.form['heightFeet']
			else:
				hFeet = ""
				
			#height inches
			if request.form['heightIn']:
				hInches = request.form['heightIn']
			else:
				hInches = ""
				
			#Total inches	
			totalHeight = (int(hFeet) * 12) + int(hInches)
			
			#weight
			if request.form['weight']:
				totalWeight = request.form['weight']
			else:
				totalWeight = ""
				
			#bmi
			calculated_bmi = (int(totalWeight) / (int(totalHeight) * int(totalHeight))) * 703
			
			#Get users db id
			query = """SELECT id
				FROM user_data
				WHERE user_name = :username"""

			user_id = db.query(query, username=request.form['username']).first().id
		
			#Insert health data
			query = """INSERT INTO health (user_id, height, weight, bmi) 
				VALUES (:userid, :height, :weight, :bmi)"""

			db.query(query, 
				userid=user_id,
				height=totalHeight, 
				weight=totalWeight,
				bmi=calculated_bmi)
		
		
		return 1


#-----------------------------------------------------------------------
#Confirmation email after registration
#-----------------------------------------------------------------------
def confirmRegistration(request):
	send_to = request.form['email']
	email_subject = "Welcome to Exercise Tracker"
	email_body = ('<h3>Welcome!</h3><br><br>'
		'Thanks for registering with '
		'Exercise Tracker. We hope you enjoy tracking your fitness!<br><br>'
		'User name: %s' % (request.form['username']))
	
	sendEmail(send_to, email_subject, email_body)


#-----------------------------------------------------------------------
#Send basic email with given parameters
#-----------------------------------------------------------------------
def sendEmail(send_to, email_subject, email_body, attachment=None, images=None):
	#Logo file name/path
	file_name = "headerLogobw.png"
	file_path = "./static/img/" + file_name

	#Msg headers
	msg = MIMEMultipart('alternative')
	msg['From'] = config.EMAIL_FROM
	msg['To'] = send_to
	msg['Subject'] = email_subject

	#Add any images (that come from the email blast)
	for attr, value in images.__dict__.items():
		if str(attr[:6]) == 'chart_':
			img = open('./downloads/' + value, 'rb').read()
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
		attachment = "./downloads/" + attachment
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
#Dashboard placeholder
#-----------------------------------------------------------------------
@app.route('/dashboard', methods=['GET','POST'])
def dashboard():
	if session['username']:
		username = session['username']
		
	return render_template('dashboard.html', username=username)
	
	
	
	
#-----------------------------------------------------------------------
#User Settings Page
#-----------------------------------------------------------------------
@app.route('/user_settings', methods=['GET','POST'])
def user_settings():
	if session['username']:
		db = connectDB()				 
		query = 'SELECT id, user_name, fname, lname, email, city, state FROM user_data where user_name = :user_name'
		user_info = db.query(query, user_name=session['username']).first()
		
		return render_template('user_settings.html', userInfo=user_info)
		
	flash('User Profile not recognized. Please log in again.', 'is-error')
	return render_template('index.html')




#-----------------------------------------------------------------------
#User Settings Page - Update Info Request
#-----------------------------------------------------------------------
@app.route('/update_info', methods=['GET','POST'])
def updateInfo():
	if request.method == 'POST':
		if update_userinfo(request):
			#only defining 'is-error' to get red text for better visibility
			flash(('Your information has been updated.'), 'is-error')
		else:
			flash('Your information was unable to be updated. Please try again later.', 'is-error')

	# return to page
	return redirect(url_for('user_settings'))



#-----------------------------------------------------------------------
#Update user's info
#-----------------------------------------------------------------------
def update_userinfo(request):
	try:
		db = connectDB()
		query = """UPDATE user_data
				SET fname=:first_name, lname=:last_name, email=:user_email, city=:user_city, state=:user_state
				WHERE id=:user_id"""

		db.query(query, first_name=request.form['firstname'], 
			last_name=request.form['lastname'],
			user_email=request.form['email'],
			user_city=request.form['city'],
			user_state=request.form['state'],
			user_id=request.form['uid'])
	
		return 1
	
	except:
		return 0



#-----------------------------------------------------------------------
#User Settings Page - Export History Request
#-----------------------------------------------------------------------
@app.route('/export_history', methods=['GET','POST'])
def exportHistory():
	if request.method == 'POST':
		try:
			return getCSV(request)
			
		except Exception as e:
			flash(('An error occurred while requesting history:  ' + str(e)), 'is-error')

	# return to page
	return redirect(url_for('user_settings'))
	


#-----------------------------------------------------------------------
#download user's activity/health history as a csv file from the downloads directory
#help from: #http://flask.pocoo.org/docs/1.0/api/?highlight=send_from_directory#flask.send_from_directory
#Request form contents:
	#request.form['uid']
	#request.form['data_type'] (activity or health)
	#request.form['length'] (all, day, week, month)
	#request.form['method'] (download, email)
#-----------------------------------------------------------------------
def getCSV(request):
	db = connectDB()
	
	#Determine time frame
	if request.form['length'] == 'all':
		if request.form['data_type'] == 'activity':
			#Download all activity history
			query = ('SELECT activity_type, duration, distance, time_created '
					'FROM activities WHERE user_id=:userID')
			
		else:
			#Download all health history
			query = ('SELECT height, weight, bmi, time_created '
					'FROM health WHERE user_id=:userID')
		
	
		#Perform Query
		rows = db.query(query,userID=request.form['uid'])

		
	else:
		#Get time frame
		today = d = datetime.today()
		if request.form['length'] == 'day':
			start_day = today - timedelta(days=1)
			
		elif request.form['length'] == 'week':
			start_day = today - timedelta(days=7)
			
		elif request.form['length'] == 'month':
			start_day = today - timedelta(days=30)
			
		else:
			raise Exception('Invalid Request')

		
		#Determine data type
		if request.form['data_type'] == 'activity':
			#Download activity history
			query = ('SELECT activity_type, duration, distance, time_created '
					'FROM activities WHERE user_id=:userID '
					'AND DATE(time_created) >= DATE(:startDay) '
					'AND DATE(time_created) <= DATE(:endDay)')
			
		else:
			#Download health history
			query = ('SELECT height, weight, bmi, time_created '
					'FROM health WHERE user_id=:userID '
					'AND DATE(time_created) >= DATE(:startDay) '
					'AND DATE(time_created) <= DATE(:endDay)')
	
	
		#Perform Query
		rows = db.query(query, userID=request.form['uid'],startDay=start_day,endDay=today)
	
		
	if len(rows.as_dict()) == 0:
		raise Exception('No History')
	
	#write results to file
	filename = request.form['data_type']+"_history.csv"
	f = open('downloads/' + filename, "w")
	f.write(rows.export('csv'))
	f.close()

	#Download file
	if request.form['method'] == 'download':
		return send_from_directory('downloads', filename, as_attachment=True)
	
	#Send email with CSV attachment
	elif request.form['method'] == 'email':
		#Get user email & user_name
		query = ('SELECT user_name, email '
				'FROM user_data WHERE id=:userID')
		user = db.query(query,userID=request.form['uid']).first()
		
		mail_to = user.email
		mail_subject = request.form['data_type'] + " history"
		mail_body = """<h3>Hello %s,</h3><br>
					Here is your requested history.<br><br>
					Keep on tracking!<br><br><br>
					<i>Thanks,<br>
					<b>The Exercise Tracker Team</b></i><br><br>
					<img src='cid:headerLogo' width='175px'>""" % (user.user_name)
					
		sendEmail(mail_to, mail_subject, mail_body, filename)

	#only defining 'is-error' to get red text for better visibility
	flash(('Your requested data has been emailed.'), 'is-error')
	return redirect(url_for('user_settings'))



#-----------------------------------------------------------------------	
#Subscribe to email summaries
#-----------------------------------------------------------------------
@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
	if request.method == 'POST':
		db = connectDB()
		
		#Check if user exists first - currently only allowing 1 subscription per user
		query = """SELECT COUNT(*) user_count
					FROM emails
					WHERE user_id = :uid"""

		user_count = db.query(query, uid=request.form['uid']).first().user_count

		if user_count > 0:
			flash(('You have already subscribed to an email summary. At this time only one subscription per user can be accommodated. If you would like to change your subscription, please unsubscribe first, then subscribe to the summary of your choice. Thank you'), 'is-error')
		
		else:
			#Insert main user data into 'user_data' table
			query = """INSERT INTO emails (user_id, schedule) 
				  VALUES (:userID, :freq)"""
		
			#Perform Query
			rows = db.query(query, userID=request.form['uid'],freq=request.form['schedule'])

			#only defining 'is-error' to get red text for better visibility
			flash(('Your email subscription preference has been saved.'), 'is-error')
		
		
	return redirect(url_for('user_settings'))



#-----------------------------------------------------------------------	
#Subscribe to email summaries
#-----------------------------------------------------------------------
@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
	if request.method == 'POST':
		db = connectDB()
		#Insert main user data into 'user_data' table
		query = """DELETE FROM emails
			  WHERE user_id = :userID"""
	
		#Perform Query
		rows = db.query(query, userID=request.form['uid'])

		#only defining 'is-error' to get red text for better visibility
		flash(('You have been removed from all email subscriptions.'), 'is-error')
		
		
	return redirect(url_for('user_settings'))
	
	

#-----------------------------------------------------------------------	
#Password reset page
#-----------------------------------------------------------------------
@app.route('/pwreset', methods=['GET', 'POST'])
def pwreset():
	
	if request.method == 'POST':
		status = pswd_reset(request)
		if status == "Success":
			flash(('Your password has been reset! Please log in '
			   'with your credentials to continue.'), 'success')
			return redirect(url_for('index'))
			
		elif status == "NoUser":
			flash(('That username and email was not found'), 'is-error')
		
		elif status == "NoMatch":
			flash(('Your passwords do not match'), 'is-error')
	
	return render_template('pwreset.html')



#-----------------------------------------------------------------------	
#Password reset function - Verifies username and email, then resets password
#-----------------------------------------------------------------------
def pswd_reset(request):
	#make sure passwords match
	if request.form['password1'] != request.form['password2']:
		return "NoMatch"
	
	#query database for existing user or email
	db = connectDB()
	
	query = ('SELECT id, user_name, email '
             'FROM user_data '
             'WHERE user_name = :username AND email = :email')
				
	user_record = db.query(query, username=request.form['username'], email=request.form['email']).first()
	
	if not user_record:
		return "NoUser"
	
	#store new password
	pw_hash = bcrypt.generate_password_hash(request.form['password1']).decode('utf-8')
	query = """UPDATE user_data
			SET pswd=:pwhash
			WHERE id=:userid"""

	db.query(query, pwhash=pw_hash, userid=user_record.id)
			
	return "Success"




#-----------------------------------------------------------------------
#Function to check database for subscription emails - create and send emails as required
#Schedules are as follows:
#Daily Emails: Every day between 8 and 9am
#Weekly Emails: Every Saturday between 8 and 9am
#Monthly Emails: First of the month, between 8 and 9am
#-----------------------------------------------------------------------
def email_blast():
	print('email blast check: ', time.strftime("%A, %d. %B %Y %I:%M:%S %p")) #Tuesday, 21. May 2019 07:01:32 PM

	now = datetime.now()
	if now.hour == 8:
		print("")
		print('Checking for email subscriptions')
		print("")
		
		db = connectDB()
		
		#Daily Emails
		query = """SELECT user_id, schedule, length 
				 FROM emails 
				 WHERE schedule='day'"""
		
		#Perform Query
		rows = db.query(query)
			
		if not len(rows.as_dict()) == 0:
			makeEmail(rows, db)

		#Weekly Emails
		if time.strftime("%A") == "Saturday":
			query = """SELECT user_id, schedule, length 
					 FROM emails 
					 WHERE schedule='week'"""
			
			#Perform Query
			rows = db.query(query)
				
			if not len(rows.as_dict()) == 0:
				makeEmail(rows, db)
		
		
		#Monthly Emails
		if now.day == 1:
			query = """SELECT user_id, schedule, length 
					 FROM emails 
					 WHERE schedule='month'"""
			
			#Perform Query
			rows = db.query(query)
				
			if not len(rows.as_dict()) == 0:
				makeEmail(rows, db)
		
		
		
#-----------------------------------------------------------------------
#Function to send email blast for given userIDs
#-----------------------------------------------------------------------
def makeEmail(rows, db):
	#Loop through all users
	for r in rows:

		#Empty object to pass chart URLs to email
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
		
		#Email body intro
		body_text = ('<html><body><h3>Hello %s,</h3><br>'
					'<p>Here is your Exercise Tracker Summary.</p>' % (user_record.user_name))
		
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
				with open('./downloads/bike.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_bike = 'bike.jpg'
				makeEmail = True
			
			if maxDistRun > 0:
				final_url = (URL_PART1 + actRun[1:] + '|' + goalRun[1:] + URL_PART2 + labelsRun + URL_PART3 + str(maxDistRun+3) + URL_PART4 + 'FFFD6C,FFCE6C' + URL_PART5 + 'Running:+Distance+vs+Goal|' + history)
				img_data = requests.get(final_url).content
				with open('./downloads/run.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_run = 'run.jpg'
				makeEmail = True
			
			if maxDistSwim > 0:
				final_url = (URL_PART1 + actSwim[1:] + '|' + goalSwim[1:] + URL_PART2 + labelsSwim + URL_PART3 + str(maxDistSwim+3) + URL_PART4 + 'A1E3FC,DFA1FC' + URL_PART5 + 'Swimming:+Distance+vs+Goal|' + history)
				img_data = requests.get(final_url).content
				with open('./downloads/swim.jpg', 'wb') as handler:
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
				with open('./downloads/weight.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_weight = 'weight.jpg'
				makeEmail = True
			
			if maxBMI > 0:
				final_url = (URL_PART1 + bmi[1:] + URL_PART2 + axisLabels + URL_PART3 + str(minBMI-2) + ',' + str(maxBMI+2) + URL_PART4 + 'FF0000' + URL_PART5 + 'BMI|' + history)
				img_data = requests.get(final_url).content
				with open('./downloads/bmi.jpg', 'wb') as handler:
					handler.write(img_data)
				images.chart_bmi = 'bmi.jpg'
				makeEmail = True
			

		#Send Email
		if makeEmail == True:
			sendEmail(user_email,"Exercise Tracker Summary",body_text,None,images)
			
			


#-----------------------------------------------------------------------
#Start scheduler for email subscription service
#help from: https://stackoverflow.com/questions/21214270/scheduling-a-function-to-run-every-hour-on-flask/38501429
#-----------------------------------------------------------------------
scheduler = BackgroundScheduler()
scheduler.add_job(func=email_blast, trigger="interval", hours=1)
scheduler.start()
# Shut down the scheduler when exiting the app
atexit.register(lambda: scheduler.shutdown())



#Start server on port 10315
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10315)
