import config 		#config file
import send_email 	#send email function
import setupDB		#database connection

from flask import Flask, render_template, redirect, request, url_for, send_from_directory, flash, session
from flask_bcrypt import Bcrypt
import records
import sys
import string
import os
from datetime import datetime, timedelta


app = Flask(__name__)
bcrypt = Bcrypt(app)
app.secret_key = config.SECRET_KEY



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
	db = setupDB.connectDB()
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
	db = setupDB.connectDB()
					 
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
	
	send_email.sendEmail(send_to, email_subject, email_body)



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
		db = setupDB.connectDB()			 
		query = 'SELECT id, user_name, fname, lname, email, city, state FROM user_data where user_name = :user_name'
		user_info = db.query(query, user_name=session['username']).first()
		
		#Check for any email blast schedules to display
		query = ('SELECT e.id, e.schedule, e.length '
				'FROM emails as e INNER JOIN user_data as u '
				'ON u.user_name = :user_name')
		schedules = db.query(query, user_name=session['username'])
		if len(schedules.as_dict()) == 0:
			schedules = None
		
		return render_template('user_settings.html', userInfo=user_info, schedules=schedules)
		
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
		db =setupDB. connectDB()
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
	db =setupDB. connectDB()
	
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
					Here is your requested history.""" % (user.user_name)
					
		send_email.sendEmail(mail_to, mail_subject, mail_body, filename)

	#only defining 'is-error' to get red text for better visibility
	flash(('Your requested data has been emailed.'), 'is-error')
	return redirect(url_for('user_settings'))



#-----------------------------------------------------------------------	
#Subscribe to email summaries
#-----------------------------------------------------------------------
@app.route('/subscribe', methods=['GET', 'POST'])
def subscribe():
	if request.method == 'POST':
		db =setupDB. connectDB()
		
		#Check if selection combination exists first
		query = """SELECT COUNT(*) user_count
					FROM emails
					WHERE user_id = :uid
					AND schedule = :schedule
					AND length = :len"""

		user_count = db.query(query, uid=request.form['uid'], schedule=request.form['schedule'], len=request.form['length']).first().user_count

		if user_count > 0:
			flash(('You have already subscribed to the requested summary, but feel free to subscribe to another.'), 'is-error')
		
		else:
			#Insert main user data into 'user_data' table
			query = """INSERT INTO emails (user_id, schedule, length) 
				  VALUES (:userID, :freq, :len)"""
		
			#Perform Query
			rows = db.query(query, userID=request.form['uid'],freq=request.form['schedule'],len=request.form['length'])

			#only defining 'is-error' to get red text for better visibility
			flash(('Your email subscription preference has been saved.'), 'is-error')
		
		
	return redirect(url_for('user_settings'))



#-----------------------------------------------------------------------	
#Subscribe to email summaries
#-----------------------------------------------------------------------
@app.route('/unsubscribe', methods=['GET', 'POST'])
def unsubscribe():
	if request.method == 'POST':
		db =setupDB. connectDB()
		#Insert main user data into 'user_data' table
		query = """DELETE FROM emails
			  WHERE id = :ID"""
	
		#Perform Query
		rows = db.query(query, ID=request.form['id'])

		#only defining 'is-error' to get red text for better visibility
		flash(('You have been removed from the requested email subscription.'), 'is-error')
		
		
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
	db =setupDB. connectDB()
	
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








#Start server on port 10315
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10315)
