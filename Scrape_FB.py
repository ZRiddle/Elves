#-------------------------------------------------------------------------------
# Name:        Scrape FB
#
# Author:      zriddle
#
# Created:     21/08/2014
#-------------------------------------------------------------------------------

import facebook
import time
import datetime
import requests
from facepy import utils
import pandas as pd
import os
import pyodbc
import subprocess

#Sql Server
#cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER=L-ZRIDDLE\SQLEXPRESS;DATABASE=Zachs_DB;Trusted_Connection=yes')
#Oracle
cnxn = pyodbc.connect('DSN=My_Only_DB;PWD=q1')
cnxn.autocommit = False
print 'Connected to the Oracle DB'

#Access Token from FB app
app_id = 692001917557240 # must be integer
app_secret = "65726e30ddd49e7b2eb64d3ed7d3b7fb"
oath_access_token = utils.get_application_access_token(app_id, app_secret)

access_token = oath_access_token
# Look at ESS Profile
pagename = 'ExtraSpace'
#pagename = 'PublicStorage'
graph = facebook.GraphAPI(access_token)
pages = ['ExtraSpace','PublicStorage','CubeSmart']

#Create data frames that will be uploaded to the database
col_posts = ['Post_ID','Page_Name','Created_Time','Username','UserID','Message','Description','Like_Count','Comment_Count','Post_Type','Upload_Date']
col_comments = ['Post_ID','Comment_Number','Page_Name','Created_Time','Username','UserID','Message','Like_Count','Upload_Date']
col_likes = ['Post_ID','Like_Number','Page_Name','Username','UserID','Upload_Date']
posts_df = pd.DataFrame(columns=col_posts)
comments_df = pd.DataFrame(columns=col_comments)
likes_df = pd.DataFrame(columns=col_likes)

ID = 0
comment_row = 0
like_row = 0
#for Loop here to loop through different pages
for pagename in pages:
    profile = graph.get_object(pagename)
    #posts = graph.get_connections(profile['id'], 'posts')
    feed = graph.get_connections(profile['id'], 'feed')




    # Wrap this block in a while loop so we can keep paginating requests until
    # finished.
    last_post_date = 2014
    print 'Scraping posts from '+pagename
    while True:
        try:
            # Perform some action on each post in the collection we receive from FB
            for post in feed['data']:
                #Loop through and posts table
                temp_row1 = [-1 for i in range(11)]
                if post.has_key('message'):
                    #Post ID
                    temp_row1[0] = ID
                    #Page Name
                    temp_row1[1] = pagename
                    #Created Time
                    temp_row1[2] = datetime.datetime.strptime(post['created_time'], "%Y-%m-%dT%H:%M:%S+%f").strftime('%Y-%m-%d %H:%M:%S')
                    last_post_date = datetime.datetime.strptime(post['created_time'], "%Y-%m-%dT%H:%M:%S+%f").year
                    #Username
                    temp_row1[3] = post['from']['name'][:245]
                    #User ID
                    temp_row1[4] = post['from']['id']
                    #Message
                    temp_row1[5] = post['message'][:245]
                    #Description
                    if post.has_key('description'):
                        temp_row1[6] = post['description'][:245]
                    else:
                        temp_row1[6] = "NULL"
                    #Like Count
                    if post.has_key('likes'):
                        temp_row1[7] = len(post['likes']['data'])
                    else:
                        temp_row1[7] = 0
                    #Comment Count
                    if post.has_key('comments'):
                        temp_row1[8] = len(post['comments']['data'])
                    else:
                        temp_row1[8] = 0
                    #Post Type
                    if post.has_key('type'):
                        temp_row1[9] = post['type'][:245]
                    else:
                        temp_row1[9] = "NULL"
                    #Upload Date
                    temp_row1[10] = time.strftime('%Y-%m-%d %H:%M:%S')

                    #populate post table
                    posts_df.loc[ID] = temp_row1

                    #Loop through comments and add to comments table
                    if post.has_key('comments'):
                        comment_num = 1
                        for c in post['comments']['data']:
                            temp_row2 = [-1 for i in range(9)]
                            #Post ID
                            temp_row2[0] = ID
                            #Comment Number
                            temp_row2[1] = comment_num
                            #Page Name
                            temp_row2[2] = pagename[:245]
                            #Created Time
                            temp_row2[3] = datetime.datetime.strptime(c['created_time'], "%Y-%m-%dT%H:%M:%S+%f").strftime('%Y-%m-%d %H:%M:%S')
                            #Username
                            temp_row2[4] = c['from']['name'][:245]
                            #UserID
                            temp_row2[5] = c['from']['id']
                            #Message
                            temp_row2[6] = c['message'][:245]
                            #Like Count
                            if c.has_key('likes'):
                                temp_row2[7] = len(c['likes']['data'])
                            else:
                                temp_row2[7] = 0
                            #Upload Date
                            temp_row2[8] = time.strftime('%Y-%m-%d %H:%M:%S')

                            comments_df.loc[comment_row] = temp_row2
                            comment_row+=1
                            comment_num+=1
                    else:
                        temp_row2 = [ID,-1,-1,'1900-01-01 00:00:00',-1,-1,"NULL",0,time.strftime('%Y-%m-%d %H:%M:%S')]
                        comments_df.loc[comment_row] = temp_row2
                        comment_row+=1
                    #Loop through likes and add to table
                    if post.has_key('likes'):
                        like_num = 1
                        for k in post['likes']['data']:
                            temp_row3 = [-1 for i in range(6)]
                            #Post ID
                            temp_row3[0] = ID
                            #
                            temp_row3[1] = like_num
                            #Page Name
                            temp_row3[2] = pagename[:245]
                            #Username
                            temp_row3[3] = k['name'][:245]
                            #UserID
                            temp_row3[4] = k['id']
                            #Upload Date
                            temp_row3[5] = time.strftime('%Y-%m-%d %H:%M:%S')
                            likes_df.loc[like_row] = temp_row3
                            like_row+=1
                            like_num+=1
                    else:
                        temp_row3 = [ID,-1,-1,-1,-1,time.strftime('%Y-%m-%d %H:%M:%S')]
                        likes_df.loc[like_row] = temp_row3
                        like_row+=1
                    #increment Post ID
                    ID+=1


            #Check the year of the last post
            if last_post_date<2014:
                print ''+str(ID)+' posts parsed.'
                print '2013 Post detected. Loop broken.'
                break

            # Attempt to make a request to the next page of data, if it exists.
            feed = requests.get(feed['paging']['next']).json()
        except KeyError:
            # When there are no more pages (['paging']['next']), break from the
            # loop and end the script.
            break

    #Delete Old data for this page
    cursor = cnxn.cursor()
    cursor.execute("DELETE FROM FB_Post_Dim WHERE Page_Name=?;",pagename)
    cnxn.commit()
    cursor.execute("DELETE FROM FB_Comment_Dim WHERE Page_Name=?;",pagename)
    cnxn.commit()
    cursor.execute("DELETE FROM FB_Like_Dim WHERE Page_Name=?;",pagename)
    cnxn.commit()
    print 'Old data deleted from database for '+pagename

#Insert Tables into the DB
cursor.executemany("INSERT INTO FB_Post_Dim values (?, ?, to_date(?,'YYYY-MM-DD HH24:MI:SS'),\
                     SUBSTR(?,0,254),?, SUBSTR(?,0,254), SUBSTR(?,0,254), ?, ?, ?, to_date(?,'YYYY-MM-DD HH24:MI:SS'),-1);",\
                     [tuple(x) for x in posts_df.values])
cnxn.commit()
print 'New post data added to database'
cursor.executemany("INSERT INTO FB_Comment_Dim values (?, ?, ?, to_date(?,'YYYY-MM-DD HH24:MI:SS'),\
                     SUBSTR(?,0,254),?, SUBSTR(?,0,254), ?, to_date(?,'YYYY-MM-DD HH24:MI:SS'),-1);",\
                 [tuple(x) for x in comments_df.values] )
cnxn.commit()
print 'New comment data added to database'
cursor.executemany("INSERT INTO FB_Like_Dim values (?, ?, ?, ?, ?, to_date(?,'YYYY-MM-DD HH24:MI:SS'));",\
                 [tuple(x) for x in likes_df.values] )
cnxn.commit()
print 'New Like data added to database'

#Close Oracle Connection
cnxn.close()

print 'Oracle Connection Closed'

#Run R Script
print 'Running R script to analyze text'
command  = ("C:/Program Files/R/R-3.1.1/bin/x64/Rscript.exe "
            "--vanilla C:/Users/zriddle/Documents/Projects/Projects/Sentiment_Analysis/Sentiment_Analysis_Oracle_Update.R")
process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
print(process.communicate()[0:])

print 'R script Complete'



