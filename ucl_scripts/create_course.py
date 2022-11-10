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

# # To be able to use what submitty has already (abs path on submitty.cs.ucl.ac.uk is /usr/local/submitty/GIT_CHECKOUT/Submitty/sbin)
this_files_location = os.path.abspath(__file__)
submitty_sbin_dir = os.path.abspath(this_files_location + '../sbin')
sys.path.append(submitty_sbin_dir)
import adduser

def read_config_yaml(config_file):
    with open(config_file, 'r') as cf:
        course_properties = yaml.safe_load(cf)

    # FIXME add course_properties checks
    assert {'course', 'semester', 'semester_name',
            'date_start', 'date_end',
            'section', 'instructor', 'ta'} <= course_properties.keys(), \
            "One or multiple keys missing from the input file"
    if course_properties['course'] != course_properties['course'].lower():
        raise ValueError('Course name should be all in lower case.')

    return course_properties

def check_running_sudo():
    assert os.getuid() == 0, "This script needs sudo/root access"

def create_user(user):
    """creates a user using the `useradd` bash command with the `-m` flag, so it
    creates a home directory.
    """
    user = user.lower()
    assert set(user) <= (set(string.ascii_lowercase) | set(string.digits)), f"Users has to be created with ascii characters ({user})"
    cmd = f"useradd -m {user}"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode == 9 and "already" in run.stderr.decode():
        logging.info(f"👤☑ {user} existed already.")
    elif run.returncode == 0:
        logging.info(f"👤✅ {user} created.")
    else:
        logging.warning(f"👤❌ {user} creation failed: {run.stderr.decode()}.")
    # TODO: save list of users that has failed?

def create_groups(course):
    """Creates the users needed to run the course as required by submitty
    """
    course = course.lower() # Though it should be already!
    groups = [f"{course}{extra}" for extra in ['', '_tas_www', '_archive']]
    for group in groups:
        cmd = f"addgroup {group}"
        run = subprocess.run(shlex.split(cmd), capture_output=True)
        if run.returncode == 0:
            g = re.match(r'.*GID (?P<group>[0-9]+).*', run.stdout.decode())
            logging.info(f"👥✅ {group} created: GID {g.group('group')} ")
        elif run.returncode == 1 and "already" in run.stderr.decode():
            logging.info(f"👥☑ {group} existed already.")
        else:
            logging.warning(f"👥❌ {group} creation failed: {run.stderr.decode()}.")


def add_user_group(user, group):
    cmd = f"adduser {user} {group}"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode == 0:
        if "Adding" in run.stdout.decode():
            logging.info(f"👤➡👥✅ {user} added to {group}")
        elif "already" in run.stdout.decode():
            logging.info(f"👤➡👥☑ {user} is already a member of {group}")
    else:
        logging.warning(f"👤➡👥❌ {user} couldn't be added to {group}: {run.stderr.decode()}.")

def add_users_groups(instructors, tas, course):

    # FIXME check instructor and tas are lists
    system_users = ['submitty_php', 'submitty_daemon', 'submitty_cgi']

    # Checks users exist
    badusers = []
    for user in instructors + tas + system_users:
        cmd = f"id {user}"
        run = subprocess.run(shlex.split(cmd), capture_output=True)
        if run.returncode != 0:
            badusers.append(f"{user} - Error: {run.stderr.decode()}")
    assert not badusers, "The following users don't exist!\n" + "\n".join(badusers)

    # Check groups exist
    groups = [f"{course}{extra}" for extra in ['', '_tas_www', '_archive']] + ['submitty_course_builders']
    badgroups = []
    for group in groups:
        cmd = f"getent group {group}"
        run = subprocess.run(shlex.split(cmd), capture_output=True)
        if run.returncode != 0:
            badgroups.append(f"{group} - Error: {run.stderr.decode()}")
    assert not badgroups, "The following groups don't exist!\n" + "\n".join(badgroups)

    for instructor in instructors:
        for group in groups:
            add_user_group(instructor, group)

    for ta in tas + system_users:
        add_user_group(ta, f"{course}_tas_www")


def create_submitty_semester(semester, semester_name, date_start, date_end):
    """ Creates a semester using submitty tool.
    """
    semester = int(semester)
    semester_name = semester_name.lower()

    # TODO Check if semester already exists from sql using sqlalchemy
    sql_command = f"select count(*) from terms where name = '{semester_name}' and term_id = '{semester:02d}';"
    psql_cmd = f"psql -d submitty -c \\\"{sql_command}\\\""
    cmd = f"su postgres -c \"{psql_cmd}\""
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode == 0: # Command run OK!
        db_exists = bool(int(run.stdout.decode().splitlines()[2])) # 0 is false
        if db_exists:
            logging.info(f"🗓☑ {semester:02d}:{semester_name} already exists.")
            return
    else:
            logging.warning(f"🗓❓ Querying for {semester:02d}:{semester_name} has produced an error: {run.stderr.decode()}.")

    # Run command to generate the semester
    script = "/usr/local/submitty/sbin/create_term.sh"
    cmd = f"{script} {semester:02d} {semester_name} {date_start:%m/%d/%Y} {date_end:%m/%d/%Y}"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode != 0:
        raise RuntimeError(f"Something has gone wrong creating the semester:\n {run.stderr.decode()}")
    logging.info(f"🗓✅ {semester:02d}:{semester_name} created.")

def create_course_directory(course, instructor):
    """ A private repository directory is needed with the permissions for the main instructor and appropriate groups.
    """
    private_course_repos = Path('/var/local/submitty/private_course_repositories')
    course_dir = private_course_repos / course
    course_dir.mkdir(parents=True, exist_ok=True)

    shutil.chown(private_course_repos, user='submitty_daemon', group='submitty_course_builders')
    shutil.chown(course_dir, user=instructor, group=f"{course}_tas_www")
    os.chmod(course_dir, stat.S_IRWXU | stat.S_IRWXG | stat.S_ISGID)

def create_submitty_course(semester, course, instructor):
    semester = int(semester)

    # Run command to generate the course
    script = "/usr/local/submitty/sbin/create_course.sh"
    cmd = f"{script} {semester:02d} {course} {instructor} {course}_tas_www"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode != 0:
        raise RuntimeError(f"Something has gone wrong creating the course {course}:\n {run.stderr.decode()}")
    logging.info(f"📚✅ {semester:02d}:{course} created.")


def add_submitty_course_section(semester, course, section):
    semester = int(semester)

    # Insert entry on db
    sql_command = f"insert into courses_registration_sections values('{semester:02d}', '{course}', '{section}');"
    psql_cmd = f"psql -d submitty -c \\\"{sql_command}\\\""
    cmd = f"su postgres -c \"{psql_cmd}\""
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode == 0: # Command run OK!
        logging.info(f"📚➡🗓✅ Semester {semester:02d} is linked with {course} and {section}.")
    else:
       logging.warning(f"📚➡🗓❓ Linking {course} and {section} with Semester {semester:02d} has produced an error: {run.stderr.decode()}.")

def add_submitty_users(users):
    """
    user is a dictionary with: firstname, lastaname, email and passwd
    """
    engine, connection = adduser.connect_db()

    for user, properties in users.items():
        users_table, user_res = adduser.get_user(user, engine, connection)
        if user_res is not None:
            logging.info(f"👤☑ {user} already exists in submitty.")
        else:
            # NOTE: Assuming AUTHENTICATION_METHOD == 'DatabaseAuthentication':
            update = {
                'user_id': user,
                'user_firstname': properties['firstname'],
                'user_preferred_firstname': properties['firstname'],
                'user_lastname': properties['lastname'],
                'user_email': properties['email'],
                'user_password': adduser.get_php_db_password(properties['password']),
            }
            query = users_table.insert()
            connection.execute(query, **update)
            logging.info(f"👤✅ {user} added to submitty.")


def add_submitty_instructor_course(course, instructor, semester):
    """
    Adds an instructor to a course, NOTE: the user needs to exist first!
    """
    semester = int(semester)

    # Run submitty command to add user to db
    script = "/usr/local/submitty/sbin/adduser_course.py"
    cmd = f"{script} {instructor} {semester:02d} {course} null"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode != 0:
        raise RuntimeError(f"Something has gone wrong adding {instructor} for {course}:\n {run.stderr.decode()}")
    logging.info(f"👨‍🏫➡📚✅ {instructor} added to {semester:02d}:{course}.")


def create_symlinks_instructor(course, semester, instructor):
    semester = int(semester)

    user_path = Path(f"/home/{instructor}/{course}")
    course_path = Path(f"/var/local/submitty/courses/{semester:02d}/{course}")

    if course_path.exists() and not user_path.exists():
        user_path.symlink_to(course_path)
        _user = shutil._get_uid(instructor)
        _group = shutil._get_gid(instructor)
        os.chown(user_path, _user, _group, follow_symlinks=False)
        logging.info(f"👨‍🏫➡📚🗃✅ {instructor} has now a local directory {user_path}.")
    elif user_path.exists():
        logging.info(f"👨‍🏫➡📚🗃☑ {instructor} had already the directory {user_path}.")

def restart_php():
    cmd = "service php7.4-fpm restart"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    if run.returncode != 0:
        logging.warning(f"PHP not restarted\n {run.stderr.decode()}")
    else:
        logging.info("PHP restarted")


def add_keys_users(user, ssh):
    """
    adds ssh keys to the users that provide them.
    """
    user_path = Path(f"/home/{user}/.ssh")
    user_path.mkdir(parents=True, exist_ok=True)
    user_key = user_path / "authorized_keys"
    with open(user_key, 'a') as auth_f:
        auth_f.write(f"{ssh}\n")
    shutil.chown(user_path, user=user, group=user)
    shutil.chown(user_key, user=user, group=user)
    os.chmod(user_path, stat.S_IRWXU)
    os.chmod(user_key, stat.S_IRUSR | stat.S_IWUSR)
    logging.info(f"🔐 ssh-key added for {user}.")

def main():
    parser = ArgumentParser(description="Creates a course and users on Submitty")
    parser.add_argument('inputfile', help="Input yaml file with the information needeed.")
    # TODO Add a remove flag to cleanout users, files, etc.
    arguments = parser.parse_args()

    # read config
    course_properties = read_config_yaml(arguments.inputfile)
    main_instructor = list(course_properties['instructor'].keys())[0]
    # create term
    create_submitty_semester(course_properties['semester'],
                             course_properties['semester_name'],
                             course_properties['date_start'],
                             course_properties['date_end'])

    # create users
    all_users = dict(course_properties['instructor'], **course_properties['ta'])
    for user in all_users:
        create_user(user)
    # Add users to submitty
    add_submitty_users(all_users)

    # create groups
    create_groups(course_properties['course'])
    add_users_groups(list(course_properties['instructor'].keys()),
                     list(course_properties['ta'].keys()),
                     course_properties['course'])

    # create course (for main instructor)
    create_course_directory(course_properties['course'],
                            main_instructor)


    create_submitty_course(course_properties['semester'],
                           course_properties['course'],
                           main_instructor)

    # Insert section on db
    add_submitty_course_section(course_properties['semester'],
                                course_properties['course'],
                                course_properties['section'])


    # Add instructors_course
    for instructor, properties in course_properties['instructor'].items():
        add_submitty_instructor_course(course_properties['course'],
                                       instructor,
                                       course_properties['semester'])
        # Create soft link for main instructor
        create_symlinks_instructor(course_properties['course'],
                                   course_properties['semester'],
                                   instructor)

        if 'sshkey' in properties:
            add_keys_users(instructor, properties['sshkey'])

    # Restart service
    restart_php()

    # Print message to main instructor
    print(f"To build a section go into ~{main_instructor}/{course_properties['course']} and run:")
    print(f"   ./BUILD_{course_properties['course']}.sh [exercise]")


if __name__ == '__main__':
    check_running_sudo()
    # TODO: Check whether this logs.
    logging.basicConfig(filename='create_course.log', level=logging.DEBUG)
    main()
