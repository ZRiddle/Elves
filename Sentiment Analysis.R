 ##Sentiment Analysis
##Naive Bayes Classifier
##Want to use 2-grams in the future


##Load Library
library(RODBC)
library(stringr);

bad_stuff <- "[0123456789~!@#$%^&*(){}_+:\"<>?,./;'[]-=]" 

##Connect to database
strDBserver = "ESSBODB"
dbhandle <-odbcConnect(strDBserver)
cat(paste("Connected to Database",strDBserver, "\n"))


good_google_reviews<-sqlQuery(dbhandle,"SELECT top 600 COMMENTS, SCORE
                                        FROM [MARKETING].[WEB].[WEB_REVIEW_FACT] f
                                        INNER JOIN [MARKETING].[WEB].[WEB_REVIEW_DIM] d
                                        ON f.WEB_REVIEW_KEY = d.WEB_REVIEW_KEY
                                        WHERE REVIEW_SITE = 'Google' 
                                        AND SCALE = 5 
                                        AND SCORE = 5
                                        AND len(comments)>2
                                        ORDER BY REVIEW_DATE desc")
bad_google_reviews<-sqlQuery(dbhandle," SELECT top 600 COMMENTS, SCORE
                                        FROM [MARKETING].[WEB].[WEB_REVIEW_FACT] f
                                        INNER JOIN [MARKETING].[WEB].[WEB_REVIEW_DIM] d
                                        ON f.WEB_REVIEW_KEY = d.WEB_REVIEW_KEY
                                        WHERE REVIEW_SITE = 'Google' 
                                        AND SCALE = 5 
                                        AND SCORE = 1
                                        AND len(comments)>2
                                        ORDER BY REVIEW_DATE desc")

qry<-"SELECT COMMENTS, MAX(SCORE) SCORE
      FROM [MARKETING].[WEB].[WEB_REVIEW_FACT] f
      INNER JOIN [MARKETING].[WEB].[WEB_REVIEW_DIM] d
      ON f.WEB_REVIEW_KEY = d.WEB_REVIEW_KEY
      WHERE REVIEW_SITE = 'Yelp!' AND SCORE IN (1,5)
      GROUP BY COMMENTS"

#get reviews and scores
data<-sqlQuery(dbhandle,qry)

#Change all to lower case
data[,1]<-tolower(data[,1])
good_google_reviews[,1]<-tolower(good_google_reviews[,1])
bad_google_reviews[,1]<-tolower(bad_google_reviews[,1])

#Change 1s to 0s
data[data[,2]==1,2]<-0
good_google_reviews[good_google_reviews[,2]==1,2]<-0
bad_google_reviews[bad_google_reviews[,2]==1,2]<-0
#Change 5s to 1s
data[data[,2]==5,2]<-1
good_google_reviews[good_google_reviews[,2]==5,2]<-1
bad_google_reviews[bad_google_reviews[,2]==5,2]<-1

#sample same amount of positive and negative
ct<-min(length(which(data[,2]==1)),length(which(data[,2]==0)))
good<-sample(1:length(data[which(data[,2]==1),1]),ct)
bad<-sample(1:length(data[which(data[,2]==0),1]),ct)
d1<-data[which(data[,2]==1),]
d1<-d1[good,]
d2<-data[which(data[,2]==0),]
d2<-d2[bad,]
#Add google reviews in
data1<-rbind(d1,d2,good_google_reviews,bad_google_reviews)
data<-rbind(data,good_google_reviews,bad_google_reviews)

#Create Table to store all words and score counts
words<-data.frame(matrix(c("",0,0),nrow=1),stringsAsFactors=FALSE)
names(words)<-c("Word","Count_Positive","Count_Negative")

for(i in 1:length(data1[,1])){
  
  str<-as.character(data1[i,1])
  score<-data1[i,2]
  
  #Remove Punctuation and Numbers
  str<-str_replace_all(str,"'","")
  str<-str_replace_all(str, "[^[:alnum:]]", " ")
  str<-str_replace_all(str,"[0,1,2,3,4,5,6,7,8,9]","")
  
  word_list<-unlist(str_split(str," "))
  ##negation handling
  negates<-which(word_list %in% c("not","no","never","zero","cannot","cant","wont"))
  word_list[negates+1]<-paste("!",word_list[negates+1],sep="")
  word_list<-unique(word_list)
  for(k in word_list){
    #add word if it doesn't exist
    if(!(k %in% words[,1])){
      #Laplace Smoothing - give an initial estimate of 1 obs in each class
      words<-rbind(words,c(k,1,1))
    }
    #increment word count
    if(score==1){
      words[which(words[,1]==k),2]<-as.numeric(words[which(words[,1]==k),2])+1
    }
    else{
      words[which(words[,1]==k),3]<-as.numeric(words[which(words[,1]==k),3])+1
    }
  }  
}

#Ignore Stop Words - Lose accuracy
#stop_words<-c("","and","the","to","a","i","is","in","of","my","this","was","storage",
#              "with","that","have","it","they","you","for","are","but","at")
stop_words<-c("")
words[,2]<-as.numeric(words[,2])
words[,3]<-as.numeric(words[,3])
words$percent_Positive<-words[,2]/(words[,2]+words[,3])
#order words by counts
words<-words[order(-words[,2]-words[,3]),]
#remove Stop Words
words<-(words[-which(words[,1] %in% stop_words),])

##Calculate P(x|1) and P(x|0)
words1<-length(which(words[,2]>0))
words0<-length(which(words[,3]>0))
words$"P(x|1)"<-words[,2]/words1
words$"P(x|0)"<-words[,3]/words0

#Use subset of all words
words_backup<-words
words<-words_backup


#Feed data back into model
data$"P(Good)"<-0
data$word_ct<-0

for(i in 1:length(data[,2])){
  str<-tolower(data[i,1])
  str<-str_replace_all(str,"'","")
  str<-str_replace_all(str, "[^[:alnum:]]", " ")
  str<-str_replace_all(str,"[0,1,2,3,4,5,6,7,8,9]","")
  
  word_list<-unlist(str_split(str," "))
  word_list<-word_list[which(!(word_list==""))]
  ##negation handling
  negates<-which(word_list %in% c("not","no","never","zero","cannot","cant","wont","dont"))
  word_list[negates+1]<-paste("!",word_list[negates+1],sep="")
  word_list<-unique(word_list)
  
  p1<-words[which(words[,1] %in% word_list),5]
  p0<-words[which(words[,1] %in% word_list),6]
  
  #P_Good<-prod(p1*120)/(prod(p1*120)+prod(p0*120))
  P_Good<-exp(sum(log(p1/p0)))/(1+exp(sum(log(p1/p0))))
  #cat(prod(p1*120),"\n")
  data[i,3]<-round(P_Good,6)
  data[i,4]<-length(unique(word_list))
}

#Find optimal cutoff
wrong_ct<-function(x){
  length(which(data$"P(Good)"<=x & data$SCORE==1))+
    length(which(data$"P(Good)">x & data$SCORE==0))
}
#plot
x1<-0:9999/50000
y1<-lapply(x1,wrong_ct)
y1<-unlist(list(y1))
plot(x1,y1,type='l')

#set optimal cutoff
opt_cutoff<-x1[which(y1==min(y1))]
cat("Optimal Cutoff =",opt_cutoff,"\n")

#compute likelyhoods
words$Positive_Likelyhood<-words[,5]/words[,6]
words$Negative_Likelyhood<-words[,6]/words[,5]

#see best and worst words
head(words[order(-words[,7]),c(1,2,3,7)],20)
head(words[order(words[,7]),c(1,2,3,8)],20)

#words[which(str_detect(words[,1],"rate")),c(1,2,3,7)]

#Error
1-(length(which(data[,3]<=opt_cutoff & data[,2]==1))+
    length(which(data[,3]>opt_cutoff & data[,2]==0)))/
   (length(data[,3]))

mean(data[which(data[,2]==0),4])
mean(data[which(data[,2]==1),4])

hist(data[which(data[,2]==0),4],nclass=50,
     main='Review Length for 1 Star, Avg=89 words',xlim=c(0,300))
hist(data[which(data[,2]==1),4],nclass=50,
     main='Review Length for 5 Star, Avg=45 words',xlim=c(0,300))

test_words<-"Wait till you start getting the rent increases every few months..."
tstr<-tolower(test_words)
tstr<-str_replace_all(tstr,"'","")
tstr<-str_replace_all(tstr, "[^[:alnum:]]", " ")
tstr<-str_replace_all(tstr,"[0,1,2,3,4,5,6,7,8,9]","")
tlist<-unlist(str_split(tstr," "))
tlist<-tlist[which(!(tlist==""))]

for(word in tlist){
  out<-words[which((words[,1]==word)),c(1,2,3,4)]
  cat(paste(out[1],out[4],"\n"))
}

##End Training Set
####################################
####################################
#Test Set

# 
# good_google_reviews$"P(Good)"<-0
# bad_google_reviews$"P(Good)"<-0
# 
# 
# 
# for(i in 1:length(good_google_reviews[,2])){
#   str<-tolower(good_google_reviews[i,1])
#   str<-str_replace_all(str,"'","")
#   str<-str_replace_all(str, "[^[:alnum:]]", " ")
#   str<-str_replace_all(str,"[0,1,2,3,4,5,6,7,8,9]","")
#   
#   word_list<-unlist(str_split(str," "))
#   ##negation handling
#   negates<-which(word_list %in% c("not","no","never","zero","cannot","cant","wont"))
#   word_list[negates+1]<-paste("!",word_list[negates+1],sep="")
#   word_list<-unique(word_list)
#   
#   p1<-words[which(words[,1] %in% word_list),5]
#   p0<-words[which(words[,1] %in% word_list),6]
#   
#   P_Good<-prod(p1*120)/(prod(p1*120)+prod(p0*120))
#   good_google_reviews[i,2]<-round(P_Good,8)
# 
# }
# 
# for(i in 1:length(bad_google_reviews[,2])){
#   str<-tolower(bad_google_reviews[i,1])
#   str<-str_replace_all(str,"'","")
#   str<-str_replace_all(str, "[^[:alnum:]]", " ")
#   str<-str_replace_all(str,"[0,1,2,3,4,5,6,7,8,9]","")
#   
#   word_list<-unlist(str_split(str," "))
#   ##negation handling
#   negates<-which(word_list %in% c("not","no","never","zero","cannot","cant","wont"))
#   word_list[negates+1]<-paste("!",word_list[negates+1],sep="")
#   word_list<-unique(word_list)
#   
#   p1<-words[which(words[,1] %in% word_list),5]
#   p0<-words[which(words[,1] %in% word_list),6]
#   
#   P_Good<-prod(p1*120)/(prod(p1*120)+prod(p0*120))
#   bad_google_reviews[i,2]<-round(P_Good,6)
#   
# }
# 
# 
# ##Results
# 1-(length(which(good_google_reviews[,2]<=opt_cutoff))+
#    length(which(bad_google_reviews[,2]>opt_cutoff)))/
#   (length(good_google_reviews[,2])+length(bad_google_reviews[,2]))
# 
# 
# good_google_reviews[which(good_google_reviews[,2]==0),1]

odbcClose(dbhandle)

