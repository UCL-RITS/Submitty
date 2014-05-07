/* Copyright (c) 2014, Chris Berger, Jesse Freitas, Severin Ibarluzea,
Kiana McNellis, Kienan Knight-Boehm, Sam Seng

All rights reserved.
This code is licensed using the BSD "3-Clause" license. Please refer to
"LICENSE.md" for the full license.
*/

#include <iostream>
#include <fstream>
#include <sstream>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>
#include <iterator>
#include <typeinfo>
#include <sys/types.h>
#include <sys/stat.h>
#include <math.h>

#include "../modules/modules.h"
#include "TestCase.h"

/* TODO: how to include this specifically? */
/*  maybe -include with g++ */
#include "../validation/config.h"

bool checkValidDirectory( char* directory );
bool checkValidDirectory( const char* directory );
int validateTestCases( char* submit_dir, char* grade_dir, int subnum, const char* subtime, int readme, int compiled );

int main( int argc, char* argv[] ) {
	
	/* Check argument usage */
	if( argc != 6 ) {
#ifdef DEBUG		
		std::cerr << "VALIDATOR USAGE: validator <user path> <submission#> <submission time> <readme result> <compile result>" << std::endl;
#endif		
		return 1;
	}
	
	// User path: ".../CSCI1200/results/{hw#}/{user}/"
	
	char submission_dir[strlen(argv[1])+strlen(argv[2])+2];
	sprintf(submission_dir, "%s%s/", argv[1], argv[2]);
	submission_dir[strlen(submission_dir)] = '\0';
	
	char grade_dir[strlen(submission_dir)+strlen("GRADES/")+1];
	sprintf(grade_dir, "%sGRADES/", submission_dir);
	grade_dir[strlen(grade_dir)] = '\0';
	
	std::cout << grade_dir << std::endl;
	
	/* Check for valid directories */
	if( !checkValidDirectory( argv[1] ) ||
	    !checkValidDirectory( submission_dir ) ||
	    !checkValidDirectory( grade_dir ) ) {

#ifdef DEBUG	    
	    std::cerr << "ERROR: one or more directories not found" << std::endl;
	    return 1;
#endif
	}
	
	// Run test cases
	int rc = validateTestCases( submission_dir, grade_dir, atoi(argv[2]), argv[3], atoi(argv[4]), atoi(argv[5]) );
	if(rc > 0) {
#ifdef DEBUG
		std::cerr << "Validator terminated" << std::endl;
#endif
		return 1;
	}
	
	return 0;
}

/* Ensures that the given directory exists */
bool checkValidDirectory( char* directory ) {
	
	if(access(directory, 0) == 0) {
		struct stat status;
		stat( directory, &status );
		if( status.st_mode & S_IFDIR ) {
#ifdef DEBUG
			std::cout << "Directory " << directory << " found!" << std::endl;
#endif
			return true;
		}
	}
#ifdef DEBUG
	std::cerr << "ERROR: directory " << directory << " does not exist"
			  << std::endl;
#endif
	return false;
}

// checkValidDirectory with const char*
bool checkValidDirectory( const char* directory ) {
	
	if(access(directory, 0) == 0) {
		struct stat status;
		stat( directory, &status );
		if( status.st_mode & S_IFDIR ) {
#ifdef DEBUG
			std::cout << "Directory " << directory << " found!" << std::endl;
#endif
			return true;
		}
	}
#ifdef DEBUG
	std::cerr << "ERROR: directory " << directory << " does not exist"
			  << std::endl;
#endif
	return false;
}

/* Runs through each test case, pulls in the correct files, validates,
   and outputs the results */
int validateTestCases( char* submit_dir, char* grade_dir, int subnum, const char* subtime, int readme, int compiled ) {

	char output_dir[strlen(submit_dir)+strlen(".submit.out/")+1];
	sprintf(output_dir, "%s.submit.out/", submit_dir);
	output_dir[strlen(output_dir)] = '\0';
	
	if(!checkValidDirectory(output_dir)) return 1;
	
	int total_grade = 0;
	
	std::stringstream testcase_json;
	
	int index = 2;
	if(compileTestCase == NULL) index--;
	int t = 1;
	for( int i = index; i < num_testcases; ++i ) {
		
		std::cout << testcases[i].title() << " - points: "
				  << testcases[i].points() << std::endl;
		
		// Pull in student output & expected output
		std::string student_path = (output_dir + testcases[i].filename());
		std::ifstream student_instr( student_path.c_str() );
		if( !student_instr ) {
#ifdef DEBUG			
			std::cerr << "ERROR: Student's " << testcases[i].filename()
					  << " does not exist" << std::endl;
#endif			
			return 1;
		}
	
		std::string expected_path = (expected_out_dir + testcases[i].expected());
		std::ifstream expected_instr( expected_path.c_str() );
		if( !expected_instr ) {
#ifdef DEBUG
			std::cerr << "ERROR: Instructor's " << testcases[i].expected()
					  << " does not exist" << std::endl;
#endif
			return 1;
		}

		//if( !student_instr || !expected_instr ) continue;
		
		char cout_temp[strlen(output_dir) + 16];
		sprintf(cout_temp, "%stest%d_cout.txt", output_dir, t );
		const char* cout_path = cout_temp;
		
		// Check cout and cerr
		/*const char* cout_path = (student_output_dir + "/test" + (char*)(i-1) +
													  "_cout.txt" ).c_str();*/
		std::ifstream cout_instr( cout_path );
		if( testcases[i].coutCheck() != DONT_CHECK ) {			
			if( !cout_instr ) { std::cerr << "ERROR: test" << t
								<< "_cout.txt does not exist" << std::endl; }			
			else {
				if( testcases[i].coutCheck() == WARN_IF_NOT_EMPTY ) {
					std::string content;
					cout_instr >> content;
					if( content.size() > 0 ) { std::cout << "WARNING: test"
							   << t << "_cout.txt is not empty" << std::endl; }
				}
				else if( testcases[i].coutCheck() == CHECK ) {
					std::cout << "Check test" << t
							<< "_cout.txt instead of output file" << std::endl;
				}
			}
		}
		
		char cerr_temp[strlen(output_dir) + 16];
		sprintf(cerr_temp, "%stest%d_cerr.txt", output_dir, t );
		const char* cerr_path = cerr_temp;
		
		/*const char* cerr_path = (student_output_dir + "/test" + (char*)(i-1) +
													  "_cerr.txt" ).c_str();*/
		std::ifstream cerr_instr( cerr_path );
		if( testcases[i].cerrCheck() != DONT_CHECK ) {
			if( !cerr_instr ) { std::cout << "ERROR: test" << t
								<< "_cerr.txt does not exist" << std::endl; }
			else {
				if( testcases[i].cerrCheck() == WARN_IF_NOT_EMPTY ) {
					std::string content;
					cerr_instr >> content;
					if( content.size() > 0 ) { std::cout << "WARNING: test"
							   << t << "_cerr.txt is not empty" << std::endl; }
				}
				else if( testcases[i].cerrCheck() == CHECK ) {
					std::cout << "Check test" << t << "_cerr.txt" << std::endl;
				}
			}
		}
		
		//std::cout << cout_path << std::endl;
		//std::cerr << cerr_path << std::endl;
		
		TestResults* result;
		const std::string blank = "";
		
		if( !student_instr && !expected_instr )
			result = testcases[i].compare( blank, blank );
		else if( !student_instr && expected_instr != NULL ) {
			const std::string e = std::string( std::istreambuf_iterator<char>(expected_instr),
										   		std::istreambuf_iterator<char>() );
			result = testcases[i].compare( blank, e );
		}
		else if( student_instr != NULL && !expected_instr ) {
			const std::string s = std::string( std::istreambuf_iterator<char>(student_instr),
										   		std::istreambuf_iterator<char>() );
			result = testcases[i].compare( s, blank );
		}
		else {
			const std::string s = std::string( std::istreambuf_iterator<char>(student_instr),
										   		std::istreambuf_iterator<char>() );
			const std::string e = std::string( std::istreambuf_iterator<char>(expected_instr),
										   		std::istreambuf_iterator<char>() );
			result = testcases[i].compare( s, e );
		}
		
		/* TODO: Always returns 0 ? */
		
		int testcase_grade = 0;
		
		char diff_path[strlen(submit_dir)+17];
		sprintf(diff_path, "%stest%d_diff.json", submit_dir, t);
		diff_path[strlen(diff_path)] = '\0';
		std::ofstream diff_stream(diff_path);
		
		/*if(typeid(result) == typeid(Difference)) {
			Difference d = (Difference)(result);
			testcase_grade = (int)floor(d.grade() * testcases[i].points());
			d.printJSON(diff_stream);
		}
		else {
			Tokens d = (Tokens)(result);
			testcase_grade = (int)floor(d.grade() * testcases[i].points());
			d.printJSON(diff_stream);
		}*/
		
		testcase_grade = (int)floor(result->grade() * testcases[i].points());
		result->printJSON(diff_stream);
		
		std::cout << "Grade: " << testcase_grade << std::endl;
		
		//int testcase_grade = (int)floor(result.grade() * testcases[i].points());
		total_grade += testcase_grade;
		
		char testcase_gradepath[strlen(grade_dir)+17];
		sprintf(testcase_gradepath, "%stest%d_grade.txt", grade_dir, t);
		testcase_gradepath[strlen(testcase_gradepath)] = '\0';
		
		std::ofstream testcase_gradefile;
		testcase_gradefile.open( testcase_gradepath );
		testcase_gradefile << testcase_grade << std::endl;
		testcase_gradefile.close();
		
		
		
		
		//result.printJSON(diff_stream);
		
		const char* last_line = (i == num_testcases-1) ? "\t\t}\n" : "\t\t},\n";
		
		// Generate JSON data
		testcase_json << "\t\t{\n"
					  << "\t\t\t\"test_name\": \"" << testcases[i].title() << "\",\n"
					  << "\t\t\t\"points_awarded\": " << testcase_grade << ",\n"
					  << "\t\t\t\"diff\":{\n"
					  << "\t\t\t\t\"instructor_file\":\"" << expected_path << "\",\n"
					  << "\t\t\t\t\"student_file\":\"" << testcases[i].filename() << "\",\n"
					  << "\t\t\t\t\"difference\":\"test" << t << "_diff.json\"\n"
					  << "\t\t\t}\n"
					  << last_line;
		++t;
		
		delete result;
	}
	
	/* Get readme and compilation grades */
	int readme_grade = (readme == 1) ? readme_pts : 0;
	const char* readme_msg = (readme == 1)? "README not found" : "README found";
	
	int compile_grade = 0;
	const char* compile_msg = "";
	if(compileTestCase != NULL) {
		compile_grade = (compiled == 1) ? compile_pts : 0;
		compile_msg = (compiled == 1)? "Compiled successfully" : "Compilation failed";
	}

	bool handle_compilation = (compileTestCase != NULL);

	total_grade += (readme_grade + compile_grade);
	
	/* Output total grade */
	char gradepath[strlen(grade_dir)+strlen("grade.txt")+1];
	sprintf(gradepath, "%sgrade.txt", grade_dir);
	gradepath[strlen(gradepath)] = '\0';
	
	std::ofstream gradefile;
	gradefile.open( gradepath );
	gradefile << total_grade << std::endl;
	gradefile.close();
	
	/* Generate submission.json */
	std::ofstream json_file("submission.json");
	json_file << "{\n"
			  << "\t\"submission_number\": " << subnum << ",\n"
			  << "\t\"points_awarded\": " << total_grade << ",\n"
			  << "\t\"submission_time\": \"" << subtime << "\",\n"
			  << "\t\"testcases\": [\n"
			  << "\t\t{\n"
			  << "\t\t\t\"test_name\": \"Readme\",\n"
			  << "\t\t\t\"points_awarded\": " << readme_grade << ",\n"
			  << "\t\t\t\"message\": \"" << readme_msg << "\",\n"
			  << "\t\t},\n";
	if(handle_compilation) {
		json_file << "\t\t{\n"
				  << "\t\t\t\"test_name\": \"Compilation\",\n"
				  << "\t\t\t\"points_awarded\": " << compile_grade << ",\n"
				  << "\t\t\t\"message\": \"" << compile_msg << "\",\n"
				  << "\t\t},\n";
	}
	json_file << testcase_json.str()
			  << "\t]\n"
			  << "}";
	json_file.close();
	
	return 0;
}

