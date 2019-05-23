import config #login/pw info
import records #Database module

#-----------------------------------------------------------------------
#Setup database connection
#-----------------------------------------------------------------------
def connectDB():
	return records.Database('postgres://{user}:{pw}@{url}/{dbName}'.format(user=config.POSTGRES_USER, pw=config.POSTGRES_PW, url=config.POSTGRES_URL, dbName=config.POSTGRES_DB))