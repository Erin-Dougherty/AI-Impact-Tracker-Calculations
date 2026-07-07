# AI Impact Tracker Calculations

This repository contains code to compute and analyze environmental impacts of ChatGPT requests including energy, carbon, and water consumption. This project also hosts a website to display analysis and data visualizations (https://aiimpacttracker.cs.haverford.edu/extension).

This repository acts as a backend to the chrome extension AI Impact Tracker: 
 - to install: https://chromewebstore.google.com/detail/ai-impact-tracker/gopcpgaafebifedebipjgfnmmiogddaj?authuser=0&hl=en
 - to view the GitHub code: https://github.com/pdelcol31/AI-Impact-Tracker

# To get started
 - The calculations folder contains the necessary code and input data to complete water, carbon, and energy calculations. This folder also hosts the FastAPI code that oversees the messaging between the chrome extension and the server.
 - The server_file folder contains the code to display information and analysis of data and for the website.

First time setting up the fastapi:
//create a new screen
screen -S ai-impact-screen
//activate the environment with the necessary dependencies (uvicorn + python code libraries)
source aiimpactvenv/bin/activate 
// activate/reload uvicorn 
uvicorn test:api --reload --port 8001 //set this to the port you are set up to listen on

How to reload the new fastapi: 
//reload your screen
screen -r ai-impact-screen
// activate/reload uvicorn 
uvicorn test:api --reload --port 8001 //set this to the port you are set up to listen on



## Ignored Data
Note: Large CSVs, log outputs, and nginx configuration files are excluded from version control 
