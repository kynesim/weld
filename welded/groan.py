"""
GROAN WITH NETHACK
"""

import os
import random

MONSTERS = [ 'a newt', 'the giant zworn of azeroth', 'arg\'s debugging skills', 
             'a giant', 'spong', 'a bad xkcd', 
             'cracked.com', 
             'webcomics!',
             'David',
             'an uncooperative radio transmitter',
             'crump']

LOCATIONS = [ 'the gnomish mines', 
              'Hogwarts',
              'Mordor',
              '23 Froome Street, Oswestry',
              'spaaaaacceeee',
              'an appalling checked shirt' ]

ITEMS = [ 'a hammer', 'a chisel', 'a camera', 'a loud hawaiian shirt',
          'the amulet of Yondar',
          'a faulty set top box' ]

def random_dict(a_dict):
    return a_dict[random.randint(0, len(a_dict)-1)]

def with_demise():
    return "You were killed by %s in %s at level %d. You had %d points. You were carrying %s."% \
        (random_dict(MONSTERS), random_dict(LOCATIONS), random.randint(1,78), 
         random.randint(0, 1000), 
         random_dict(ITEMS))


# End file.

    
