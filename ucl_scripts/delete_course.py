import logging
import os
import re
import shlex
import shutil
import stat
import string
import subprocess
import sys
from argparse import ArgumentParser
from pathlib import Path

import yaml

from create_course import check_running_sudo, read_config_yaml

#sys.path.append('/usr/local/submitty/sbin/') # To be able to use what submitty has already
sys.path.append('/home/ccaegra/Documents/submitty/Submitty/sbin')
import adduser

def delete_course_directory(semester, course):
    '''Deletes the directory associated with a course, provided it currently exists
    '''
    if os.path.exists(course_dir):
        # delete the course directory
        course_dir = Path('/var/local/submitty/courses/<SEMESTER>/<COURSE>')
    else:
        # flag that its not there
        pass
    return

def main():
    parser = ArgumentParser(description="Deletes a course on Submitty created via the create_course.py script, and disassociates the course from existing Submitty users")
    parser.add_argument('inputfile', help="Input yaml file to create_course.py.")
    parser.add_argument('-rm', '--remove-directory', dest='dir_delete_bool', action='store_true', help="Delete course directory in addition to database.")
    args = parser.parse_args()

    # read the original input file to obtain the course name and semester
    course_properties = read_config_yaml(args.inputfile)
    # for deletion, we just need the internal semester and course name that was used to create the course
    course_semester = course_properties["semester"]
    course_name = course_properties["course"]
    
    # if desired, delete the course directory
    if args.dir_delete_bool:
        delete_course_directory(course_semester, course_name)
        #rm /var/local/submitty/courses/<SEMESTER>/<COURSE>

    # Remove course database
    # sudo su postgres
    # psql -d postgres -c "DROP DATABASE submitty_<SEMESTER>_<COURSE>;"
    # !!!! but it may be necessary to first clean up connections
    # sudo su postgres
    # psql -d postgres -c "SELECT *, pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = 'submitty_<SEMESTER>_<COURSE>';"

    # remove the course and the association from all users to [of?] the course from the master database
    # sudo su postgres
    # psql -d submitty -c "DELETE FROM courses_users WHERE semester='<SEMESTER>' AND course='<COURSE>'; DELETE FROM courses WHERE semester='<SEMESTER>' AND course='<COURSE>';"

    return

if __name__=="__main__":
    check_running_sudo()
    # TODO: check whether this logs
    logging.basicConfig(filename='delete_course.log', level=logging.DEBUG)
    main()
