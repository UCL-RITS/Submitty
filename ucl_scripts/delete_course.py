import logging
import os
import shlex
import shutil
import subprocess
from argparse import ArgumentParser
from pathlib import Path

from create_course import check_running_sudo, read_config_yaml

# To be able to use what submitty has already (abs path on submitty.cs.ucl.ac.uk is /usr/local/submitty/sbin)
# submitty_sbin_dir = '/usr/local/submitty/sbin/'
# sys.path.append(submitty_sbin_dir)

def delete_course_directory(semester, course, force_delete=False):
    '''Deletes the directory associated with a course, provided it currently exists
    '''
    course_dir = Path(f'/var/local/submitty/courses/{semester}/{course}')
    if os.path.exists(course_dir):
        # course directory exists, but request user confirmation that we want to delete it if it is populated
        is_empty = (len(os.listdir(course_dir)) == 0)
        if is_empty:
            # delete the course directory SILENTLY
            os.rmdir(course_dir)
            logging.info(f"Empty course directory {course_dir} was deleted.")
        elif force_delete:
            # delete the course directory but throw a warning that it was not empty
            shutil.rmtree(course_dir)
            logging.warning(f"{course_dir} was not empty, but was force-deleted.")
        else:
            # request user confirmation to delete non-empty directory
            really_delete = input(f"{course_dir} is not empty. Confirm directory removal [yes/N]: ")
            if really_delete.lowercase()=='yes':
                # actually delete
                shutil.rmtree(course_dir)
                logging.warning(f"{course_dir} was not empty, but was force-deleted.")
            else:
                # don't delete, and terminate script
                logging.error(f"{course_dir} non-empty, course deletion aborted.")
                raise RuntimeError(f"{course_dir} non-empty, course deletion aborted.")
    else:
        # flag that its not there
        logging.info(f"Expected course directory {course_dir} does not exist, abort.")
        raise RuntimeError(f"Expected course directory {course_dir} does not exist, abort.")
    return

def take_db_backup():
    '''Takes a backup of the course database prior to deletion
    '''
    # These instructions don't actually exist on the submitty website yet:
    # https://submitty.org/sysadmin/configuration/course_creation#clean-up-existing-course
    # HELPFUL, but there's a placeholder function here in case we want to do it
    return

def cleanup_course_connections(semester, course):
    '''Cleans up potentially hanging or old connections to the course database
    '''
    postgres_cmd = "su postgres -c"
    psql_cmd = f"psql -d postgres -c \"SELECT *, pg_terminate_backend(pid) FROM pg_stat_activity WHERE pid <> pg_backend_pid() AND datname = \'submitty_{semester}_{course}\';\""
    cmd = f"{postgres_cmd} \\ {psql_cmd}"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    logging.info(f"Running command\n{cmd}")
    if run.returncode == 0:
        # Command ran OK
        logging.info(f"Successfully cleaned up connections")
    else:
        logging.error(f"Could not clean up database connections.")
        raise RuntimeError(f"Could not clean up database connections.")
    return

def remove_course_db(semester, course, skip_cleanup=False):
    '''Removes the course database, potentially cleaning up connections first
    '''
    # attempt to clean up database connections if desired
    if not skip_cleanup:
        cleanup_course_connections(semester, course)

    # delete the course database
    postgres_cmd = "su postgres -c"
    psql_cmd = f"-d postgres -c \"DROP DATABASE submitty_{semester}_{course};\""
    cmd = f"{postgres_cmd} \\ {psql_cmd}"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    logging.info(f"Running command\n{cmd}")
    if run.returncode == 0:
        # Command ran OK
        logging.info(f"Successfully deleted database submitty_{semester}_{course}")
    else:
        logging.error(f"Could not delete database submitty_{semester}_{course}")
        raise RuntimeError(f"Could not delete database submitty_{semester}_{course}")
    return

def remove_references_from_master_db(semester, course):
    '''Removes references to the deleted course from all users and the master database
    '''
    # remove all references to the course from the master database
    postgres_cmd = "su postgres -c"
    psql_cmd = f"psql -d submitty -c \"DELETE FROM courses_users WHERE semester=\'{semester}\' AND course=\'{course}\'; DELETE FROM courses WHERE semester=\'{semester}\' AND course=\'{course}\';\""
    cmd = f"{postgres_cmd} \\ {psql_cmd}"
    run = subprocess.run(shlex.split(cmd), capture_output=True)
    logging.info(f"Running command\n{cmd}")
    if run.returncode == 0:
        # Command ran OK
        logging.info(f"Successfully removed all associations to the course from the master database")
    else:
        logging.error(f"Could not remove associations from the master database")
        raise RuntimeError(f"Could not remove associations from the master database")
    return

def main():
    parser = ArgumentParser(description="Deletes a course on Submitty created via the create_course.py script, and disassociates the course from existing Submitty users.")
    parser.add_argument('inputfile', help="Input yaml file to create_course.py.")
    parser.add_argument('-rm', '--remove-directory', dest='dir_delete_bool', action='store_true', help="Delete course directory in addition to database.")
    parser.add_argument('-f', '--force-delete', dest='force_delete_flag', action='store_true', help='Forces deletion of course directory, hanging user accounts, etc, without requiring user confirmation.')
    parser.add_argument('-s', '--skip-connection-cleanup', dest='connection_cleanup_flag', action='store_true', help='Skips the connection cleanup when removing course databases.')
    args = parser.parse_args()

    # read the original input file to obtain the course name and semester
    course_properties = read_config_yaml(args.inputfile)
    # for deletion, we just need the internal semester and course name that was used to create the course
    course_semester = course_properties["semester"]
    course_name = course_properties["course"]
    
    # if desired, attempt to delete the course directory
    if args.dir_delete_bool:
        delete_course_directory(course_semester, course_name, args.force_delete_flag)

    # if desired, take database backup before deletion 
    # [CURRENTLY NOT SUPPORTED] Add argument to ArgumentParser when Submitty docs updated
    if False:
        take_db_backup()
    
    # remove course database
    remove_course_db(course_semester, course_name, args.connection_cleanup_flag)

    # remove the course, and the association from all users to the course, from the master database
    remove_references_from_master_db(course_semester, course_name)

    return

if __name__=="__main__":
    check_running_sudo()
    # TODO: check whether this logs
    logging.basicConfig(filename='delete_course.log', level=logging.DEBUG)
    main()
