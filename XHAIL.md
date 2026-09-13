# Welcome, XHAIL researcher!

This is the demo version of the DCR chatbot app. License for research use is hereby granted;
all other rights reserved.

## Setup 

To use this app, you must provide a valid token for accessing graphs
on the DCR repository.

1. Acquire a token like this:

    curl -u $USER:$PASSWORD -X POST -H 'Content-length: 0' 'https://repository.dcrgraphs.net/api/user/token?title=chatbot'

(Obviously, you'll need to set USER and PASSWORD first.)

2. Write the token in the API_KEY in file `.env`

3. Make sure you have python installed

4. Make sure you have the python packages `flask`, `request`, `dotenv`, `waitress` installed. 

## Use

Run the locally by running

    python app.py

The app is now available at [](http://localhost:8080).

Try the app out on the following models:

 - [2005521](https://www.dcrgraphs.net/Tool?id=2005521) - corono demo 
 - [2005522](https://www.dcrgraphs.net/Tool?id=2005520) - DMN demo (English)
 - [2006270](https://www.dcrgraphs.net/Tool?id=2006270) - SU Demo (Danish)

You should have received credentials for dcrgraphs.net separately. These two
graphs are available to all members of XHAIL.

If you need to change the graphs, do make a copy (menu: File -> Save As):
other's may be relying on these graphs.

## Notes

The chatbot implementation itself is a quick one-off implementation meant for demos
and hackathons. It is not production quality and not suitable for being permanently
exposed to the internet. 


