import plotly.express as px
import pandas as pd
import numpy as np

data = pd.read_csv("data/emissions.csv", header = 0)

date = data['date'].tolist()
token = data['tokens'].tolist()


print(date)
print(token)

fig1 = px.bar(data, x= date, y= token, title='Total Tokens per Day')
fig2 = px.bar(data, x= date, y= token, title='Carbon Usage per Day')
fig3 = px.bar(data, x= date, y= token, title='Water Usage per Day')

fig1.show()

fig1.write_html("/home/h302/gptfootprint/server_file/Tokens_per_day.html")
fig2.write_html("/home/h302/gptfootprint/server_file/Carbon_per_day.html")
fig3.write_html("/home/h302/gptfootprint/server_file/Water_per_day.html")
