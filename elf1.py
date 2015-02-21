
import math
import hours as hrs



class Elf:
    """ Each Elf starts with a rating of 1.0 and are available at 09:00 on Jan 1.  """
    def __init__(self, elfid):
        self.id = elfid
        self.rating = 1.0
        self.next_available_time = 0
        self.rating_increase = 1.02
        self.rating_decrease = 0.90

    def work(self, toy):
        """ Updates the elf's productivity rating and next available time based on last toy completed.
        :param hrs: Hours object for bookkeeping
        :param toy: Toy object for the toy the elf just finished
        :param start_minute: minute work started
        :param duration: duration of work, in minutes
        :return: void
        """
        toy_time = toy[0]
        self.next_available_time += toy_time
        self.update_productivity(int(math.ceil(toy_time / self.rating)))

    def update_productivity(self, toy_required_minutes):
        """ Update productivity assuming we work as many good hours as possible
        """
        # number of required minutes to build toy worked by elf, broken up by sanctioned and unsanctioned minutes
        full_days = toy_required_minutes/1440
        remaining_time = toy_required_minutes-full_days*1440
        sanctioned = full_days*600+min(remaining_time,600)
        unsanctioned = full_days*840+max(0,(remaining_time-600))
        self.rating = max(0.25,
                          min(4.0, self.rating * (self.rating_increase ** (sanctioned/60.0)) *
                              (self.rating_decrease ** (unsanctioned/60.0))))

