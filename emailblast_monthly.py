import send_email 	#script for sending email
import setupDB		#setup Database connection


#-----------------------------------------------------------------------
#Check database for subscription emails - create and send emails as required
#-----------------------------------------------------------------------

#Monthly Emails	

#Connect to database
db = setupDB.connectDB()
query = """SELECT user_id, schedule, length 
		 FROM emails 
		 WHERE schedule='Monthly'"""

#Perform Query
rows = db.query(query)
	
if not len(rows.as_dict()) == 0:
	send_email.makeEmail(rows, db)
	
send_email.log()