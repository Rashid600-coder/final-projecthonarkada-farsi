Honarkadeh Farsi is a web-based platform for human–AI interaction.
Follow the steps below to run the project locally.

1. Download the Project
First, download the My_Project folder completely.
Important:  Do not change the structure or order of the files and folders inside this directory.

2. Install Required Libraries
If the required libraries are not installed, install them using the following command:
pip install -r requirements.txt
(If requirements.txt does not exist, install the libraries listed in the project manually.)

3. Configure the API Key
Open the file server.py and:
Insert your API key on line 706.
Insert the API base URL (the website from which you obtained the API key) on line 707.
If you do not have an API key, you can obtain a limited free key for testing purposes from the following website:
https://gapgpt.app/ai-api

5. Run the Project
After configuring the API key:
Make sure your VPN or proxy is turned OFF.
Open CMD or Terminal.
Navigate to the My_Project directory.
Run one of the following commands:
python server.py
or:
python3 server.py

5. Access the Website
After running the server, a local address such as the following will be displayed:
http://127.0.0.1:5000
Copy this address and paste it into your web browser.
You will see the welcome page.
To use the full features of the website:
First, register an account.
Then, log in.
