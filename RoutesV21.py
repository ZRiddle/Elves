"""
#Author: Zach Riddle
#Date: 1/1/2015

#Title: Basic structure of elf simulation

#V1: Adding 8 routes in the end for eff > .33
#V2: Cleanup, new LP
#V3: Rating Targeting.  Added routes 9-15
#V4: Cleaned up Routes
#V5: Adding Route to Elf Class to force routes!
     -Add step after Midrange to go at least 2825.
            --idea: loop until the any elf goes below 4.0 eff and start elf.next_route at 15
     -Find a way to add misc ramp presents into Routes {[274-289],[330-342]} - need over .50 eff, ideally over .57
"""

import os
import csv
import math
import heapq
import time
import datetime
import pyodbc

from hours import Hours
from elf import Elf

# ========================================================================== #

"""
Parameters to tweak
Midrange Effeciency Cutoff - When to change from ramp to Bad
good_vs_bad_ratio - The ratio of how many good hours we need to use a ramp in bad hours.
break_even_toy_cutoff - cutoff after midrange for break-even toys
rating_threshold - Threshold to do bad present or ramp with tiny presents
"""

#High impact parameters - Fiddle!
ramp_cutoff = 4.0           #if below this, don't ramp, go do bigger present
smallest_ramp = 540         #smallest amount of time allowed to work on ramp
biggest_ramp = 1.00          #multipled by time left in day, allowed to go some % over to ramp
start_ramping_again = 3.2  #threshold to start ramping after doing midrange/overnight/big present
helper_elves = 15            #percent of elves to help with midrange - idea is to stagger start times to ramp differently
                                #1 = 0%, 2 = 50%, 3 = 67%, 4 = 75%
opt_update = 15000          #How often to update the optimization


#Probably ok - Keep for now
target_on_flag = True #enable targeting of eff if below target_threshold
target_threshold = .27 #if enabled, target the rating if rating_threshold below this

#Not impactful parameters - Don't change
good_vs_bad_ratio = 9
midrange_elfs = 1   #Only needd 1 guy here
rating_threshold = .40 #This gets dynamically updated based on supply left
lower_bound = 8500     #Dynamically updated based on supply
ref_time = datetime.datetime(2014, 1, 1, 0, 0) #Last Present arrives 2014-12-10 23:59:00.000
NUM_ELVES = 900 #don't touch this. 900 is optimal
break_even_cutoff = -math.log(.9)/math.log(1.02) #number of good hours/bad hours to break even on eff

def create_elves(NUM_ELVES):
    list_elves = []
    for i in xrange(1, NUM_ELVES+1):
        elf = Elf(i)
        heapq.heappush(list_elves, [elf.next_available_time, elf])
    return list_elves

def assign_elf_to_toy(input_time, current_elf, pres_time, hrs):
    start_time = input_time #fuck that +1 minutes thing
    duration = int(math.ceil(pres_time / current_elf.rating))
    #Update elf next available and rating
    current_elf.update_elf(hrs, pres_time, int(input_time), int(duration))

    return duration


if __name__ == '__main__':
    start = time.time()
    myelves = create_elves(NUM_ELVES)
    hrs = Hours()


    #Get Bad Toy List
    cnxn = pyodbc.connect('DRIVER={SQL Server};SERVER=ELEMENT;DATABASE=RM_Sandbox;Trusted_Connection=yes')
    cursor = cnxn.cursor()
    sql1 = ("""SELECT ToyID, cast(Duration as int) Duration, Arrival
                FROM [RM_Sandbox].[dbo].[toys_elves]
                WHERE (Duration>=2844 and Duration<=4000) OR (Duration>=8161)
                ORDER BY duration, Arrival """)
    cursor.execute(sql1)
    bad_toys = cursor.fetchall()

    for i in range(len(bad_toys)):
        bad_toys[i]=list(bad_toys[i])

    print 'Bad Toys extracted from DB'

    #Get Small Toy List
    sql2 = ("""SELECT ToyID, cast(Duration as int) Duration, Arrival
                FROM [RM_Sandbox].[dbo].[toys_elves]
                WHERE Duration<2844
                ORDER BY duration, Arrival """)
    cursor.execute(sql2)
    small_toys = cursor.fetchall()

    for i in range(len(small_toys)):
        small_toys[i]=list(small_toys[i])

    #Get Small Toy List Distinct
    sql21 = ("""SELECT distinct Duration
                FROM [RM_Sandbox].[dbo].[toys_elves]
                WHERE Duration<2844
                ORDER BY duration """)
    cursor.execute(sql21)
    small_toys1 = cursor.fetchall()

    for i in range(len(small_toys1)):
        small_toys1[i]=list(small_toys1[i])


    print 'Small toys extracted from DB'

    #Create Small Toy Dict
    small_toy_1 = {small_toys1[i][0]:[] for i in xrange(len(small_toys1))}
    i = 0
    while i < len(small_toys):
        small_toy_1[small_toys[i][1]].append(small_toys[i])
        i += 1

    #Delete lists
    small_toys = []
    small_toys1 = []

    print 'Small toys dictionary created'


    #Extract some toys for the midrange list
    midrange_toy = {}
    for i in xrange(2399,2402):
        midrange_toy.update({i:small_toy_1.pop(i)})


    #Get Overnight Toy List
    sql2 = ("""SELECT ToyID, cast(Duration as int) Duration, Arrival
                FROM [RM_Sandbox].[dbo].[toys_elves]
                WHERE Duration>4000 and Duration<8161
                ORDER BY duration, Arrival """)
    cursor.execute(sql2)
    on_toys = cursor.fetchall()

    for i in range(len(on_toys)):
        on_toys[i]=list(on_toys[i])

    #Get overnight Toy List Distinct
    sql41 = ("""SELECT distinct Duration
                FROM [RM_Sandbox].[dbo].[toys_elves]
                WHERE Duration>4000 and Duration<8161
                ORDER BY duration """)
    cursor.execute(sql41)
    on_toys1 = cursor.fetchall()

    for i in range(len(on_toys1)):
        on_toys1[i]=list(on_toys1[i])
    print 'Overnight Toys Extracted from DB'

    #Create overnight Toy Dictionary
    overnight_toy = {on_toys1[i][0]:[] for i in xrange(len(on_toys1))}
    i = 0
    while i < len(on_toys):
        overnight_toy[on_toys[i][1]].append(on_toys[i])
        i += 1


    #Create array to save info
    #ToyID - ElfID - StartTime - Duration
    output = []

    """
    Algorithm starts here:

    If .25, fill day.
    If > .25, find optimal present that takes 540-610 minutes
    If no such present exists, do a huge one.
    """

    #Reverse Bad toys so we can do them largest to smallest
    bad_toys = bad_toys[::-1]

    #Record last 1200 toys ratings
    recent_ratings = []
    for i in range(1800):
       recent_ratings.append(4.0)
    best_rating = 4.0

    overnight = math.pow(1.02,20)*math.pow(.9,14)
    good_time = math.pow(1.02,10)

    first_year_bool = True

    #Loop for small toys. Continually ramp up then do Huge present
    while len([k for k in small_toy_1.keys() if k<180])>0:

        """
        Pick next elf
        If  Rating < Threshold: Ramp
        Else: do largest bad_toy
        """
        # get next available elf
        elf_available_time, current_elf = heapq.heappop(myelves)

        rating = current_elf.rating
        if rating<=start_ramping_again:
            current_elf.hit_4_flag=0

        if first_year_bool and elf_available_time>498360:
            first_year_bool = False

        #find minutes left in the day
        min_day = 1140 - (elf_available_time-24*60*math.floor(elf_available_time/(60*24)))

        T0 = 0
        T00= 0
        Tm = 0
        T1 = 0
        rest_of_day = 0
        #Calculate tradeoffs
        if rating>=2.1:
            overnight_delta = 1
            B0 = 1.0*bad_toys[-1][1] #smallest bad_toy
            B1 = 1.0*bad_toys[0][1]  #biggest bad_toy
            r0 = (rating*good_time*math.pow(.9,B0/(60*rating)-10))

            try:
                Bm = max([k for k in overnight_toy.keys() if k<=rating*60*34]) #find next overnight toy
                overnight_delta = math.pow(1.02,-(34*60-Bm/rating)/60)
            except:
                Bm = 0

            if (Bm/rating + min_day)>(60*34) and min_day<599:
                rest_of_day = min_day

            bad_h = (B0/rating-min_day)/60
            r00 = (rating*math.pow(1.02,min_day/60)*math.pow(.9,bad_h))

            T0 = B0/rating + B1/r0 + 4*Bm + min_day                                   #Doing smallest then biggest
            Tm = 4.0*B0 + Bm/rating + B1/(rating*overnight*overnight_delta) + rest_of_day #Doing overnight toy
            T1 = 4.0*B0 + 4.0*Bm + B1/rating                                              #Doing biggest toy
            T00= B0/rating + Bm/(r0) + B1/(overnight*r0*overnight_delta) + min_day    #Doing smallest then overnight then biggest
            T000=B0/rating + Bm/r00 + B1/(overnight*r00*overnight_delta)
            T001=B0/rating + 4*Bm + B1/r00

        if min_day <= 1:
            #skip this elf and push to next day because their shitty code breaks this
            current_elf.next_available_time = int(elf_available_time+min_day+840)
            #push Elf to heapq
            heapq.heappush(myelves, (current_elf.next_available_time, current_elf))


        #Ramp if below threshold for current bad presents
        elif rating<rating_threshold:
            if target_on_flag and best_rating < target_threshold:
                #Target Rating!
                target_time = math.log(rating_threshold/rating)/math.log(1.02)*60
                #Set optimal minutes to work to find appropriate present
                #try to hit target eff if we can within the day.
                if target_time<min_day:
                    try:
                        pres_row = min(key for key in small_toy_1 if (key <=min_day*rating and key>target_time*rating))
                        flag = False
                    except:
                        try:
                            pres_row = max(key for key in small_toy_1 if key <=min_day*rating)
                            flag = False
                        except:
                            pres_row = min(small_toy_1.keys())
                            flag = True
                else: #just fill day like usual
                    try:
                        pres_row = max(key for key in small_toy_1 if key <=min_day*rating)
                        flag = False
                    except:
                        pres_row = min(small_toy_1.keys())
                        flag = True

            #else Don't target
            else:
                try:
                    pres_row = max(key for key in small_toy_1 if key <=min_day*rating)
                    flag = False
                except:
                    pres_row = min(small_toy_1.keys())
                    flag = True

            #make sure we don't lose eff
            if flag and min_day/(abs(math.ceil(pres_row/rating)-min_day)+1)<good_vs_bad_ratio and min_day<599:
                #skip elf and push him to the next day
                current_elf.next_available_time = current_elf.next_available_time+min_day+840
                #push Elf to heapq
                heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
            else:
                if first_year_bool and elf_available_time < small_toy_1[pres_row][0][2]:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
                else:
                    #Work Present
                    current_present = small_toy_1[pres_row].pop(0)

                    #Delete key if empty
                    if len(small_toy_1[pres_row])==0:
                        small_toy_1.pop(pres_row)

                    #Now Do The Present
                    work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                    #Record everything
                    tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                    time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                    output.append([current_present[0],current_elf.id,time_string,work_duration])
                    if len(output)%10000==0:
                        print len(output),'Toys down at',time_string

                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

        #if we can keep ramping, then ramp! Only ramp if present exists to work on for at least 540 minutes
        elif current_elf.hit_4_flag==0 and rating<ramp_cutoff \
        and len([k for k in small_toy_1.keys() if (k<=(min_day*biggest_ramp)*rating and k>=smallest_ramp*rating)])>0:

            try:
                pres_row = max(key for key in small_toy_1 if (key <=min_day*rating and key>=smallest_ramp*rating))
                flag = False
            except:
                pres_row = min(key for key in small_toy_1 if (key <=(min_day*biggest_ramp*rating) and key>=smallest_ramp*rating))
                flag = True

            if first_year_bool and elf_available_time < small_toy_1[pres_row][0][2]:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
            else:
                #Work Present
                current_present = small_toy_1[pres_row].pop(0)

                #Delete key if empty
                if len(small_toy_1[pres_row])==0:
                    small_toy_1.pop(pres_row)

                #Now Do The Present
                work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                #Record everything
                tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                output.append([current_present[0],current_elf.id,time_string,work_duration])
                if len(output)%10000==0:
                    print len(output),'Toys down at',time_string

                #push Elf to heapq
                heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

        #try to get rid of midrange shit first year
        elif first_year_bool and rating>=4.0 and max(small_toy_1.keys())>=2390:
            #do midrange bullshit first year.
            if min_day<600:
                #skip elf and push him to the next day
                current_elf.next_available_time = current_elf.next_available_time+min_day+840
                #push Elf to heapq
                heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
            else:
                pres_row = 0
                for k in small_toy_1.keys():
                    if k>=2390 and small_toy_1[k][0][2] < elf_available_time:
                        pres_row = k
                if pres_row == 0:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
                else:
                    #Work Present
                    current_present = small_toy_1[pres_row].pop(0)

                    #Delete key if empty
                    if len(small_toy_1[pres_row])==0:
                        small_toy_1.pop(pres_row)
                        print pres_row,"toys complete. You're Welcome midrange dude."

                    #Now Do The Present
                    work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                    #Record everything
                    tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                    time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                    output.append([current_present[0],current_elf.id,time_string,work_duration])
                    if len(output)%10000==0:
                        print len(output),'Toys down at',time_string

                    #update hit_4_flag
                    current_elf.hit_4_flag=1

                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))


        #Have elf 1 doing those midrange presents
        elif current_elf.id<=midrange_elfs and len(midrange_toy)>0:
            #do all of these at 4 effenciency and get them out of the way
            #list should go up to 2840.
            #If we have full day, do biggest present. Elf 1 will stay at 4 effenciency
            if min_day == 600:
                pres_row = max(midrange_toy.keys())
                flag = False
            else: #try fill day.
                try:
                    pres_row = max(key for key in midrange_toy if key <=min_day*rating)
                    flag = False
                except:
                    pres_row = min(midrange_toy.keys())
                    flag = True

            #make sure we don't lose eff
            if flag and min_day/(abs(math.ceil(pres_row/rating)-min_day)+1)<break_even_cutoff:
                #skip elf and push him to the next day
                current_elf.next_available_time = current_elf.next_available_time+min_day+840
                #push Elf to heapq
                heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
            else:
                if first_year_bool and elf_available_time < midrange_toy[pres_row][0][2]:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
                else:
                    #Work Present
                    current_present = midrange_toy[pres_row].pop(0)

                    #Delete key if empty
                    if len(midrange_toy[pres_row])==0:
                        midrange_toy.pop(pres_row)
                        if len(midrange_toy)%5==0:
                            print '*** Elf 1 finished',pres_row
                            print '***',len(midrange_toy),'more present times left'

                    #Now Do The Present
                    work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                    #Record everything
                    tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                    time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                    output.append([current_present[0],current_elf.id,time_string,work_duration])
                    if len(output)%10000==0:
                        print len(output),'Toys down at',time_string

                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

        #grab midrange bullshit if out of midrange presents
        elif current_elf.id<=midrange_elfs and max(small_toy_1.keys())>1800:
            max_small = max(small_toy_1.keys())
            midrange_toy.update({max_small:small_toy_1.pop(max_small)})
            #push Elf to heapq
            heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

        #else Help out the #1 guy if rating =4 and time in day is small or 600
        elif rating>=4.0 and current_elf.hit_4_flag==0 \
        and max(small_toy_1.keys())>=2390 \
        and current_elf.id%helper_elves!=0 \
        and (min_day == 600 or min_day<=10):

            if min_day<=10:
                #skip elf and push him to the next day
                current_elf.next_available_time = current_elf.next_available_time+min_day+840
                #push Elf to heapq
                heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
            else:
                #Find a midrange present
                pres_row = max(small_toy_1.keys())

                if first_year_bool and elf_available_time < small_toy_1[pres_row][0][2]:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
                else:
                    #Work Present
                    current_present = small_toy_1[pres_row].pop(0)

                    #Delete key if empty
                    if len(small_toy_1[pres_row])==0:
                        small_toy_1.pop(pres_row)
                        print pres_row,"toys complete. You're Welcome midrange dude."

                    #Now Do The Present
                    work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                    #Record everything
                    tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                    time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                    output.append([current_present[0],current_elf.id,time_string,work_duration])
                    if len(output)%10000==0:
                        print len(output),'Toys down at',time_string

                    #update hit_4_flag
                    current_elf.hit_4_flag=1

                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

        elif rating>=2.1 and (Tm<T1 or T00<T1 or T0<T1 or T000<T1 or T001<T1):
            if Tm<T00 and Tm<T0 and Tm<T000 and Tm<T001 and Bm>0:
                if (Bm/rating + min_day)>(60*34) and min_day<599:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

                else:
                    if first_year_bool and elf_available_time < overnight_toy[Bm][0][2]:
                        #skip elf and push him to the next day
                        current_elf.next_available_time = current_elf.next_available_time+min_day+840
                        #push Elf to heapq
                        heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
                    else:
                        #Do overnight present 34hours
                        current_present = overnight_toy[Bm].pop(0)

                        #Delete key if empty
                        if len(overnight_toy[Bm])==0:
                            overnight_toy.pop(Bm)
                            print "Finished off",Bm,'overnight toy'

                        if current_elf.id%121==0:
                            print 'Doing',current_present[1],'midrange toy'
                            print 'Next Bad toy =',bad_toys[0][1]

                        #assign to elf
                        work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                        #Record everything
                        tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                        time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                        output.append([current_present[0],current_elf.id,time_string,work_duration])
                        if len(output)%10000==0:
                                print len(output),'Toys down at',time_string

                        #push Elf to heapq
                        heapq.heappush(myelves, (current_elf.next_available_time, current_elf))


            else:
                bad_h = (B0/rating-min_day)/60
                Time_gained = B1/(rating*math.pow(1.02,min_day/60)*math.pow(.9,bad_h)) - B1/r0
                if min_day < Time_gained and min_day<599:
                    #skip elf and push him to the next day
                    current_elf.next_available_time = current_elf.next_available_time+min_day+840
                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

                else:
                    if first_year_bool and elf_available_time < bad_toys[-1][2]:
                        #skip elf and push him to the next day
                        current_elf.next_available_time = current_elf.next_available_time+min_day+840
                        #push Elf to heapq
                        heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

                    else:
                        #Do smallest bad_present
                        current_present = bad_toys.pop(len(bad_toys)-1)

                        if current_elf.id%121==0:
                            print 'Doing',current_present[1],'midrange toy'
                            print 'Next Bad toy =',bad_toys[0][1]

                        #assign to elf
                        work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                        #Record everything
                        tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                        time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                        output.append([current_present[0],current_elf.id,time_string,work_duration])
                        if len(output)%10000==0:
                                print len(output),'Toys down at',time_string

                        #push Elf to heapq
                        heapq.heappush(myelves, (current_elf.next_available_time, current_elf))


        #Else, do big present, kill elf, start over
        else:

            #Is it worth it to wait a day and ramp?
            if rating<ramp_cutoff and len([k for k in small_toy_1.keys() if (k<=600*rating and k>=565*rating)])>0\
            and bad_toys[0][1]/rating>(bad_toys[0][1]/min(4,(rating*math.pow(1.02,max([k for k in small_toy_1.keys() if \
            (k<=600*rating and k>=565*rating)])/60)))+min_day) and min_day<599:
                #skip elf and push him to the next day
                current_elf.next_available_time = current_elf.next_available_time+min_day+840
                #push Elf to heapq
                heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

            else:
                if first_year_bool and elf_available_time < bad_toys[0][2]:
                        #skip elf and push him to the next day
                        current_elf.next_available_time = current_elf.next_available_time+min_day+840
                        #push Elf to heapq
                        heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

                else:
                    #Take next bad toy
                    current_present = bad_toys.pop(0)

                    #assign to elf
                    work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

                    #Record everything
                    tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
                    time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
                    output.append([current_present[0],current_elf.id,time_string,work_duration])
                    if len(output)%10000==0:
                            print len(output),'Toys down at',time_string

                    #push Elf to heapq
                    heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

                    #Do optimization for the new rating threshold
                    if len(bad_toys)%opt_update==0 and bad_toys[0][1]>8880:
                        #calculate remaining supply
                        cost = 0
                        for k in small_toy_1.keys():
                            if k<100:
                                cost+=k*len(small_toy_1[k])*3.2
                            elif k<150:
                                cost+= k*len(small_toy_1[k])*3.3
                            elif k<180:
                                cost+=k*len(small_toy_1[k])*3.2
                            elif k<200:
                                cost+=k*len(small_toy_1[k])*3
                            elif k <210:
                                cost+=k*len(small_toy_1[k])/.35
                            elif k <230:
                                cost+=k*len(small_toy_1[k])/.39
                        #Turn cost to hours
                        cost = cost/60

                        #calculate all costs in terms of next bad present
                        T01 = min(20000,bad_toys[0][1])
                        Sum1 = 0.0001
                        n = 0
                        for k in range(len(bad_toys)):
                            if bad_toys[k][1]>lower_bound and bad_toys[k][1]<19000:
                                Sum1 += math.sqrt(1.0*bad_toys[k][1]/T01)
                                n += 1

                        #Next bad_present should get this many hours
                        h = (cost + n/.0225 - Sum1/.0225)/Sum1
                        #Next target effencSiency is .25*1.02^h
                        rating_threshold = .25*(1+.0225*h)
                        #update lower bound
                        lower_bound = T01/math.pow((1+.0225*h),2)

                        print 'Current Supply =',cost,'hours.'
                        print 'Next optimal eff =',rating_threshold,'for toy =',bad_toys[0][1]
                        print 'Best recent eff =',best_rating/1.05,'New Lower Bound =',lower_bound
                        rating_threshold = min(.38,rating_threshold)

                    #record ratings here
                    recent_ratings.append(rating)   #add most recent
                    recent_ratings.pop(0)           #delete oldest one
                    best_rating = max(recent_ratings)*1.05

                    #steal some small presents for midrange
                    if best_rating<0.9:
                        steal_list = [k for k in small_toy_1.keys() if k>best_rating*600 and k >170]
                        if len(steal_list)>0:
                            for s in steal_list:
                                midrange_toy.update({s:small_toy_1.pop(s)})
                                print '*Max Rating only',best_rating/1.05,'Stealing',s,'from the small list'
    #-------------------------------------------------------------------------------------------------


    #add overnight toys back into bad_toys
    for k in overnight_toy.keys():
        for j in range(len(overnight_toy[k])):
            bad_toys.append(overnight_toy[k].pop())

    print '---------------------------------------------------------'
    print 'Small presents exhausted, Time to plow through the rest'
    print 'Largest Present Remaining =',bad_toys[0][1]
    print '---------------------------------------------------------'

    bad_toys = bad_toys[::-1]

    #Out of small presents.
    #Just gotta burn through the rest of the bad presents.
    #No breaks. Start Asap
    while len(bad_toys)>0:

        # get next available elf
        elf_available_time, current_elf = heapq.heappop(myelves)
        rating = current_elf.rating

        #find minutes left in the day
        min_day = 1140 - (elf_available_time-24*60*math.floor(elf_available_time/(60*24)))

        if min_day <= 1:
            #skip this elf and push to next day because their shitty code breaks this
            current_elf.next_available_time = int(elf_available_time+min_day+840)
            #push Elf to heapq
            heapq.heappush(myelves, (current_elf.next_available_time, current_elf))
        else:
            #Assign largest Bad Toy, doesn't matter how much time is left
            current_present = bad_toys.pop(0)

            #assign to elf
            work_duration = assign_elf_to_toy(elf_available_time, current_elf, current_present[1], hrs)

            #Record everything
            tt = ref_time + datetime.timedelta(seconds=60*elf_available_time)
            time_string = " ".join([str(tt.year), str(tt.month), str(tt.day), str(tt.hour), str(tt.minute)])
            output.append([current_present[0],current_elf.id,time_string,work_duration])
            if len(output)%10000==0:
                    print len(output),'Toys down at',time_string

            #push Elf to heapq
            heapq.heappush(myelves, (current_elf.next_available_time, current_elf))

    print '---------------------------------------------------------'
    print 'total runtime = {0}'.format(time.time() - start)
    print 'Score = ',hrs.convert_to_minute(output[len(output)-1][2])*math.log(901)
    print '---------------------------------------------------------'

    #Write to CSV File
    soln_file = os.path.join(os.getcwd(), 'output27.csv')
    with open(soln_file,"wb") as f:
        writer = csv.writer(f)
        writer.writerow(['ToyId', 'ElfId', 'StartTime', 'Duration'])
        writer.writerows(output)

    print 'csv file complete'

