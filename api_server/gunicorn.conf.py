# Define the number of workers for your app. Between 4 and 12 should be fine.
workers = 4
worker_class = "uvicorn.workers.UvicornWorker"

# Define on which port the webserver will be listening. If you have a webserver already listening to port 80
# you should proxy requests to below port to the app
bind = ":80"

# If using an https connection (you should), define your SSL keys and certificate locations here
keyfile = None
certfile = None

accesslog = "/var/lib/topologic/api_server/access.log"
errorlog = "/var/lib/topologic/api_server/error.log"
chdir = "/var/lib/topologic/api/"
