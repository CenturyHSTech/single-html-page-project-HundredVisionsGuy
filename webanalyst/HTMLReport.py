import logging
import re

import file_clerk.clerk as clerk
import webcode_tk.html as html
import webcode_tk.validator as val
from bs4 import BeautifulSoup

import webanalyst.report as rep

logging.basicConfig(
    format="%(asctime)s - %(message)s", datefmt="%d-%b-%y %H:%M:%S"
)
report_template_path = "webanalyst/report_template.html"
report_path = "report/report.html"


class HTMLReport:
    def __init__(self, readme_list, dir_path):
        self.__dir_path = dir_path
        self.html_level = "0"
        self.__readme_list = readme_list
        self.html_requirements_list = []
        self.html_files = []
        self.linked_stylesheets = {}
        self.style_tags = []
        self.validator_errors = {"HTML": {}, "CSS": {}}
        self.validator_warnings = {"HTML": {}, "CSS": {}}
        self.report_details = {
            "html_level": "",
            "can_attain_level": False,
            "html_level_attained": None,
            "validator_goals": 0,
            "uses_inline_styles": False,
            "validator_results": {"CSS Errors": 0, "HTML Errors": 0},
            "num_html_files": 0,
            "required_elements": {
                "HTML5_essential_elements": {
                    "DOCTYPE": 1,
                    "HTML": 1,
                    "HEAD": 1,
                    "TITLE": 1,
                    "BODY": 1,
                },
            },
            "required_elements_found": {
                "HTML5_essential_elements_found": {},
            },
            "meets_required_elements": {
                "meets_HTML5_essential_elements": False,
                "meets_other_essential_elements": False,
            },
            "required_nested_elements": [],
            "actual_nested_elements": [],
            "meets_required_nested_elements": {},
            "meets_requirements": True,
        }

    def generate_report(self):
        self.get_html_files_list()
        self.get_html_requirements_list()
        self.get_html_level()
        self.get_validator_goals()
        self.set_required_nested_elements()
        self.get_required_nested_elements()
        self.ammend_required_elements()
        self.set_linked_stylesheets()
        self.analyze_results()
        self.publish_results()

    def get_html_files_list(self):
        self.html_files = clerk.get_all_files_of_type(self.__dir_path, "html")
        return self.html_files

    def get_required_elements(self):
        # get a list of all required elements: the keys
        required_elements = []
        for element in enumerate(
            self.report_details["required_elements"].keys()
        ):
            if element[1] == "HTML5_essential_elements":
                for nested_el in enumerate(
                    self.report_details["required_elements"][
                        "HTML5_essential_elements"
                    ].keys()
                ):
                    required_elements.append(nested_el[1])
            else:
                required_elements.append(element[1])
        return required_elements

    def get_validator_goals(self):
        """gets number of validator errors allowed"""
        readme_list = self.html_requirements_list[:]
        # Looking for Allowable Errors
        for line in readme_list:
            if "* Allowable Errors" in line:
                allowable_errors = re.search("[0-9]", line).group()
                self.report_details["validator_goals"] = int(allowable_errors)
                return int(allowable_errors)
            else:
                continue
        return 0

    def set_required_elements_found(self):
        # get a copy of the required elements
        required_elements = self.get_required_elements().copy()

        # remove the HTML5_essential_elements
        # that was already covered
        html_essential_elements = ["DOCTYPE", "HTML", "HEAD", "TITLE", "BODY"]
        for i in html_essential_elements:
            required_elements.remove(i)

        # iterate through each element and get the total number
        # then compare to required number
        for el in required_elements:
            double_el = ""
            if "or" in el:
                # we have 2 elements and either may work
                # split the two elements and check each 1 at a time
                # if one meets, they both meet (or else they don't)
                actual_number = 0
                double_el = el
                my_elements = el.split("`")
                for i in my_elements:
                    if "or" in i:
                        continue
                    actual_number += html.get_num_elements_in_folder(
                        i, self.__dir_path
                    )
                el = my_elements[0] + "` or `" + my_elements[-1]
            else:
                actual_number = html.get_num_elements_in_folder(
                    el, self.__dir_path
                )

            # get how many of that element is required
            number_required = self.report_details["required_elements"][el]

            # do we have enough of that element to meet?
            el_meets = actual_number >= number_required

            # edit the el if it has two by removing the back tics `
            if double_el:
                el = el.replace("`", "")

            # modify the report details on required elements found
            self.report_details["required_elements_found"][el] = [
                number_required,
                actual_number,
                el_meets,
            ]

    def set_html5_required_elements_found(self):
        # Get HTML5_essential_elements
        html5_elements = self.report_details["required_elements"][
            "HTML5_essential_elements"
        ].copy()
        # get # of html files in folder - this is our multiplier
        for el in enumerate(html5_elements):
            element = el[1].lower()
            # how many were found
            number_found = html.get_num_elements_in_folder(
                element, self.__dir_path
            )
            number_required = self.report_details["required_elements"][
                "HTML5_essential_elements"
            ][element.upper()]
            # there must be 1 for each page
            number_required = len(self.html_files)
            element_meets = (
                number_found == number_required and number_required > 0
            )

            self.report_details["required_elements_found"][
                "HTML5_essential_elements_found"
            ][element.upper()] = [number_required, number_found, element_meets]

    def meets_required_elements(self):
        all_elements_meet = True  # assume they meet until proved otherwise
        # Get all essential_elements
        html5_elements = self.report_details["required_elements"].copy()
        html5_elements.pop("HTML5_essential_elements", None)
        # remove essential HTML5 elements
        print(html5_elements)
        # check all other tags to see if they meet -
        # record whether each one meets individually
        for i in enumerate(html5_elements.items()):
            all_elements_meet = True
            key, min_value = i[1]
            actual_value = html.get_num_elements_in_folder(
                key, self.__dir_path
            )
            element_meets = actual_value >= min_value
            if not element_meets:
                all_elements_meet = False  # it just takes one not meeting
        return all_elements_meet

    def check_element_for_required_number(self, file_path, element, min_num):
        num_elements = html.get_num_elements_in_file(element, file_path)
        return num_elements >= min_num

    def get_html_requirements_list(self):
        h_req_list = []
        # create a flag to switch On when in the HTML section and off
        # when that section is over (### CSS)
        correct_section = False
        for row in enumerate(self.__readme_list):
            # 1st row in the section should be ### HTML
            if row[1] == "### HTML":
                # it's the beginning of the correct section
                correct_section = True
            if row[1] == "### CSS":
                break
            if correct_section:
                h_req_list.append(row[1])

        self.html_requirements_list = h_req_list
        return self.html_requirements_list

    def get_html_level(self):
        # extract HTML level from readme_list
        for i in self.__readme_list:
            if "### HTML Level" in i:
                self.report_details["html_level"] = i
                break
        row_list = re.split("=", self.report_details["html_level"])
        self.report_details["html_level"] = row_list[1].strip()
        self.html_level = self.report_details["html_level"]
        return self.report_details["html_level"]

    def get_num_html_files(self):
        html_files = clerk.get_all_files_of_type(self.__dir_path, "html")
        return len(html_files)

    def can_attain_level(self):
        # Determine whether or not this project is enough
        # to qualify to meet the level
        description = ""
        for i in range(len(self.__readme_list)):
            row = self.__readme_list[i]
            if "### HTML Level" in row:
                # set description to next row (after the header)
                description = self.__readme_list[i + 1]
                break
        self.report_details["can_attain_level"] = "does meet" in description
        return "does meet" in description

    def ammend_required_elements(self):
        """adds remaining required HTML elements"""
        # extract all elements and their minimum #
        # using a regex to capture the pattern: `EL` : ##
        ptrn = r"((`(.*)`\s*):(\s*\d*))"
        for i in self.html_requirements_list:
            if "`DOCTYPE`" in i:
                # skip the row with required HTML 5 elements
                continue
            match = re.search(ptrn, i)
            if match:
                key, val = match.group(2, 4)
                key = key.strip()[1:-1]
                # add key and value to required elements
                self.report_details["required_elements"][key] = int(val)

    def get_report_details(self):
        return self.report_details

    def validate_html(self):
        # create a dictionary with doc titles for keys
        # and num of errors for value
        num_errors = 0  # initialized
        # get titles and run them through validator
        for file_path in self.html_files:
            # Get error objects
            errors_in_file = val.get_markup_validity(file_path)
            # Get number of errors
            num_errors = len(errors_in_file)
            page_name = clerk.get_file_name(file_path)
            if num_errors > 0:
                self.process_errors(page_name, errors_in_file)
        error_goal = self.report_details.get("validator_goals")
        if num_errors > error_goal:
            self.report_details.get("validator_results")["HTML Meets"] = False
        else:
            self.report_details.get("validator_results")["HTML Meets"] = True

    def process_errors(self, page_name, errors):
        """receives errors and records warnings and errors"""
        errors_dict = {"HTML": {}, "CSS": {}}
        warnings_dict = {"HTML": {}, "CSS": {}}

        # Loop through all the errors and separate
        # error from warning and CSS from HTML
        # Must use try/except whenever adding an item
        # because it will crash if we try and append it
        # to a non-existant list
        for item in errors:
            if item["type"] == "error":
                if "CSS" in item["message"]:
                    self.report_details["validator_results"]["CSS Errors"] += 1
                    try:
                        errors_dict["CSS"][page_name].append(item)
                    except Exception as e:
                        errors_dict["CSS"][page_name] = [
                            item,
                        ]
                        print("We have an exception: " + str(e))
                else:
                    self.report_details["validator_results"][
                        "HTML Errors"
                    ] += 1
                    try:
                        errors_dict["HTML"][page_name].append(item)
                    except Exception as e:
                        errors_dict["HTML"][page_name] = [
                            item,
                        ]
                        print("We have an exception " + str(e))
            elif item["type"] == "info":
                if "CSS" in item["message"]:
                    try:
                        warnings_dict["CSS"][page_name].append(item)
                    except Exception as e:
                        warnings_dict["CSS"][page_name] = [
                            item,
                        ]
                        print("We have an exception " + str(e))
                else:
                    try:
                        warnings_dict["HTML"][page_name].append(item)
                    except Exception as e:
                        warnings_dict["HTML"][page_name] = [
                            item,
                        ]
                        print("We have an exception " + str(e))
            elif item["type"] == "alert":
                try:
                    warnings_dict["HTML"][page_name].append(item)
                except Exception as e:
                    warnings_dict["HTML"][page_name] = [
                        item,
                    ]
                    print("We have an exception " + str(e))

        self.augment_errors(
            errors_dict
        )  # we might need to change to a function
        self.add_warnings(warnings_dict)

    def augment_errors(self, new_dict):
        """appends any errors from a dict to validator errors"""
        for page, errors in new_dict["HTML"].items():
            self.validator_errors["HTML"][page] = errors

    def add_warnings(self, warnings):
        for page, warning in warnings["HTML"].items():
            self.validator_warnings["HTML"][page] = warning

    def add_errors(self, errors):
        for page, error in errors["HTML"].items():
            self.validator_errors[page] = error

    def analyze_results(self):
        self.can_attain_level()
        self.validate_html()
        self.set_html5_required_elements_found()
        self.set_required_elements_found()
        self.meets_required_elements()
        self.meets_html5_essential_requirements()
        self.check_for_inline_styles()
        self.meets_overall()

    def publish_results(self):
        # Get report
        report_content = html.get_html(report_path)

        # HTML Overview Table
        html_overview_tr = self.get_html_overview_row()
        report_content.find(id="html-overview").replace_with(html_overview_tr)

        # Validation Report
        # HTML Validation
        # get the results of the validation as a string
        validation_results_string = self.get_validation_results_string("HTML")

        # create our tbody contents
        tbody_contents = BeautifulSoup(
            validation_results_string, "html.parser"
        )
        tbody_id = "html-validation"
        report_content.find(id=tbody_id).replace_with(tbody_contents)

        # CSS Validation
        # get the results of the validation as a string
        validation_results_string = self.get_validation_results_string("CSS")

        # create our tbody contents
        tbody_contents = BeautifulSoup(
            validation_results_string, "html.parser"
        )
        tbody_id = "css-validation"
        report_content.find(id=tbody_id).replace_with(tbody_contents)

        # Generate Error report
        # For HTML Errors
        error_report_contents = self.get_validator_error_report()
        tbody_contents = BeautifulSoup(error_report_contents, "html.parser")
        tr_id = "html-validator-errors"
        report_content.find(id=tr_id).replace_with(tbody_contents)

        # For CSS Errors
        error_report_contents = self.get_validator_error_report("CSS")
        tbody_contents = BeautifulSoup(error_report_contents, "html.parser")
        tr_id = "css-validator-errors"
        report_content.find(id=tr_id).replace_with(tbody_contents)

        html_goals_results = list(
            self.report_details["required_elements_found"].items()
        )
        html5_goals_results = list(html_goals_results.pop(0)[1].items())

        html_elements_results_string = ""
        # we have to modify an entire tbody (not just a tr)
        tbody_id = "html-elements-results"
        for el in html5_goals_results:
            # get element, goal, actual, and results
            element = el[0]
            goal = el[1][0]
            actual = el[1][1]
            results = str(el[1][2])
            html_elements_results_string += (
                rep.Report.get_report_results_string(
                    "", element, goal, actual, results
                )
            )
        # add remaining elements
        for el in html_goals_results:
            # get element, goal, actual, and results
            element = el[0]
            goal = el[1][0]
            actual = el[1][1]
            results = el[1][2]
            html_elements_results_string += (
                rep.Report.get_report_results_string(
                    "", element, goal, actual, results
                )
            )
        ######
        ######
        # create our tbody contents
        tbody_contents = BeautifulSoup(
            html_elements_results_string, "html.parser"
        )
        report_content.find(id=tbody_id).replace_with(tbody_contents)

        # Publish nested HTML results
        nested_html_results = self.report_details.get("actual_nested_elements")
        nested_html_results_str = ""
        tbody_id = "nested-html-elements-results"
        for result in nested_html_results:
            container = result.get("container")
            children = result.get("expected_children")
            description = result.get("result_description")
            meets = str(result.get("meets"))
            nested_html_results_str += rep.Report.get_report_results_string(
                "", container, children, description, meets
            )
        # create our tbody contents
        tbody_contents = BeautifulSoup(nested_html_results_str, "html.parser")
        report_content.find(id=tbody_id).replace_with(tbody_contents)

        # Check the overall HTML goals to see if it meets or not
        output = '<div id="overall-results">'
        if self.report_details.get("meets_requirements"):
            output += (
                '<p><strong class="success">Congratulations! your project'
            )
            output += (
                "meets all elements of the HTML goals!</strong></p></div>"
            )
        else:
            output = '<p><strong class="warning">Sorry, but your project does '
            output += "not meet in one or more category of the HTML"
            output += " goals</strong></p>"

        div_contents = BeautifulSoup(output, "html.parser")
        div_id = "overall-results"
        report_content.find(id=div_id).replace_with(div_contents)

        # Save new HTML as report/report.html
        with open(report_path, "w") as f:
            f.write(str(report_content.contents[0]))

    def get_html_overview_row(self):
        # get a string version of can_attain_level
        can_attain = str(self.can_attain_level())
        html_overview_string = rep.Report.get_report_results_string(
            "html-overview", self.html_level, can_attain, "", ""
        )
        overview_row = BeautifulSoup(html_overview_string, "html.parser")
        return overview_row

    def get_validation_results_string(self, validation_type="HTML"):
        results = ""
        if not self.validator_errors.get("HTML"):
            return '<tr><td rowspan="4">Congratulations! No Errors Found</td></tr>'
        else:
            try:
                validation_report = self.validator_errors[
                    validation_type
                ].copy()
            except Exception as e:
                print("Whoah Nelly")
                print("We have an exception " + str(e))
            cumulative_errors = 0
            for page, errors in validation_report.items():
                num_errors = len(errors)
                error_str = str(num_errors) + " error"
                if num_errors != 1:
                    error_str += "s"
                cumulative_errors += num_errors
                cumulative_errors_string = (
                    str(cumulative_errors) + " total errors"
                )
                meets = str(
                    cumulative_errors <= self.report_details["validator_goals"]
                )
                results += rep.Report.get_report_results_string(
                    "", page, error_str, cumulative_errors_string, meets
                )
            return results

    def get_validator_error_report(self, validation_type="HTML"):
        results = ""
        if not self.validator_errors:
            # write 1 column entry indicating there are no errors
            congrats = "Congratulations, no errors were found."
            results = '<tr><td colspan="4">' + congrats + "</td></tr>"
            return results
        else:
            errors_dict = self.validator_errors[validation_type]
            tr_class = "html-validator-errors"

            for page, errors in errors_dict.items():
                for error in errors:
                    message = error["message"]

                    # clean message of smart quotes for HTML rendering
                    message = message.replace("“", '"').replace("”", '"')
                    last_line = error["lastLine"]
                    try:
                        first_line = error["firstLine"]
                    except Exception as e:
                        first_line = last_line
                        print("We have an exception " + str(e))
                    last_column = error["lastColumn"]
                    try:
                        first_column = error["firstColumn"]
                    except Exception as e:
                        first_column = last_column
                        print("We have an exception " + str(e))
                    # render any HTML code viewable on the screen
                    extract = (
                        error["extract"]
                        .replace("<", "&lt;")
                        .replace(">", "&gt;")
                    )

                    # place extract inside of a code tag
                    extract = "<code>" + extract + "</code>"

                    location = "From line {}, column {}; to line {}, column {}.".format(
                        first_line, first_column, last_line, last_column
                    )

                    new_row = rep.Report.get_report_results_string(
                        tr_class, page, message, location, extract
                    )
                    new_row = new_row.replace("Meets", extract)
                    results += new_row
        return results

    def extract_el_from_dict_key_tuple(self, the_dict):
        """converts all keys from a tuple to 2nd item in tuple"""
        new_dict = {}
        for t, i in the_dict.items():
            new_dict[t[1]] = i
        return new_dict

    def meets_html5_essential_requirements(self):
        required_elements = self.report_details["required_elements_found"][
            "HTML5_essential_elements_found"
        ]
        for element in required_elements.values():
            if not element[-1]:
                return False
        return True

    def set_required_nested_elements(self):
        html_requirements = self.html_requirements_list
        nested_requirements = []
        start = 0
        stop = 0
        for i in range(len(html_requirements)):
            stop = i + 1
            if start > 0 and "*" in html_requirements[i]:
                stop = i
            if "Required Nested" in html_requirements[i]:
                start = i + 1
        if stop == 0:
            nested_requirements = html_requirements[start:]
        else:
            nested_requirements = html_requirements[start:stop]
        for req in nested_requirements:
            datum = {}
            num_count = re.findall(r"\d", req)
            num_count = int(num_count[0])
            split_data = req.split(":")
            container = self.get_container(split_data[0])
            children = self.get_children(split_data[1])
            datum = {container: {}}
            datum[container]["count"] = num_count
            datum[container]["children"] = children
            self.report_details["required_nested_elements"].append(datum)

    def get_container(self, text: str) -> str:
        """returns the element name from the backtics

        Args:
            text: the text from the README file that contains
                a single element in back tics

        Returns:
            element: the element inside of the back tics"""

        element = text.split("`")[1]
        return element

    def get_children(self, text: str) -> list:
        """Returns a list of all elements from the string.

        We will count the number of backtics and divide by two
        to get the official number of elements we are looking for.
        Then we'll use the split method to split by back tic
        and grab just the elements ignoring all other text.

        Args:
            text: this is the text from the README file that
                indicates all child elements from the container

        Returns:
            elements: a list of all child elements that we are
                looking for.
        """
        elements = []
        num_elements = text.count("`")
        num_elements /= 2
        num_elements = int(num_elements)
        split_text = text.split("`")
        for i in range(len(split_text)):
            if i % 2 == 1:
                elements.append(split_text[i])
        return elements

    def get_required_nested_elements(self):
        # Get a list of required containers and their required children
        details = self.report_details.get("required_nested_elements")
        results = []
        for detail in details:
            container = detail.keys()
            container = list(container)[0]
            content = detail.get(container)
            single_result = self.prep_nested_results(container, content)
            children = content.get("children")
            sorted_children = children[:]
            sorted_children.sort()
            files = self.get_html_files_list()
            for file in files:
                elements = html.get_elements(container.lower(), file)
                if elements:
                    for element in elements:
                        result = {element.name: []}
                        for child in children:
                            target = "<" + child.lower()
                            contents = str(element.contents)
                            if target in contents:
                                result[element.name].append(child)
                        results.append(result)
            count_goal = detail.get(container).get("count")

            matches = count_goal
            for items in results:
                actual_children = list(items.values())
                missing_child = False
                for child in sorted_children:
                    if child not in actual_children[0]:
                        missing_child = True
                if missing_child:
                    matches -= 1
                    print("This element does not meet")
                else:
                    # good news, we have a single winner
                    single_result["number_meeting"] += 1
            self.process_single_result(single_result)

    def prep_nested_results(self, container: str, content: dict) -> dict:
        """Prepares a dictionary for the results of a nested element goal.

        The goal of this method is to prep the details for displaying the
        details of whether a particular nested tag goal is met or not and
        put it into plain English.

        Args:
            container: the element that should contain children.

            content: how many containers there should be, and which
                elements should be nested in that container.

        Returns:
            single_result: the dictionary that will hold the details of the
                result of one goal.
        """
        count_goal = content.get("count")
        children = content.get("children")
        single_result = {
            "container": container,
            "count_goal": count_goal,
            "expected_children": children,
            "number_meeting": 0,
            "meets": False,
            "result_description": "",
        }
        return single_result

    def process_single_result(self, result: dict):
        """Returns a human readable description of the results of a
        nested container goal

        This processes the results of a single nested element goal to
        determine whether it meets or not and creates a human readable
        description of the goal and whether it meets or not for the
        report.

        Args:
            result (dict): a dictionary of the results
        """
        goal = result.get("count_goal")
        actual = result.get("number_meeting")
        children = result["expected_children"]
        num_children = len(children)
        result["meets"] = actual >= goal
        description = "There should be " + str(goal) + " <code>"
        if goal == 1:
            description += result["container"] + "</code> element with "
        else:
            description += result["container"] + "</code> elements, each with "
        description += str(num_children) + " nested "
        if num_children == 1:
            description += "element inside: <code>"
        else:
            description += "elements inside: <code>"
        for i in range(num_children):
            if num_children == 1:
                description += children[i] + "</code>. "
            elif num_children == 2 and i == num_children - 1:
                description += " and " + children[i] + ". "
            elif num_children > 2 and i == num_children - 1:
                description += ", and " + children[i] + ". "
            else:
                description += children[i] + "</code>"
        if result["meets"]:
            description += (
                "Congratulations! Your project meets because you have "
            )
        else:
            description += "Sorry, but your project does not meet because you "
            description += "only have "
        description += str(actual) + " <code>" + result["container"]
        if actual > 1:
            description += (
                "</code> elements with the required number of children."
            )
        else:
            description += (
                "</code> element with the required number of children."
            )
        result["result_description"] = description
        self.report_details["actual_nested_elements"].append(result)

    def set_linked_stylesheets(self):
        """will generate a list of HTML docs and the CSS they link to"""
        linked = {}
        # loop through html_files
        # in each file get the href of any link if that
        # href matches a file in the folder
        for file in self.html_files:
            contents = clerk.file_to_string(file)
            link_hrefs = clerk.get_linked_css(contents)
            filename = clerk.get_file_name(file)
            linked[filename] = link_hrefs
        self.linked_stylesheets = linked

    def check_for_inline_styles(self):
        files_with_inline_styles = []
        for file in self.html_files:
            markup = clerk.file_to_string(file)
            has_inline_styles = html.uses_inline_styles(markup)
            if has_inline_styles:
                filename = clerk.get_file_name(file)
                files_with_inline_styles.append(filename)

        self.report_details["uses_inline_styles"] = files_with_inline_styles

    def meets_overall(self):
        """does the HTML report meet (overall meets or not).

        This methods checks all areas of the HTML report wherever there is
        a meets or not (based on the report) and determines whether the HTML
        meets all requirements.
        """
        meets = True
        meets_required = self.report_details.get("meets_required_elements")
        for result in meets_required.values():
            if not result:
                meets = False
                break
        nested_results = self.report_details.get("actual_nested_elements")
        for result in nested_results:
            if not result.get("meets"):
                meets = False
                break
        meets_validator = self.report_details.get("validator_results").get(
            "HTML Meets"
        )
        if not meets_validator:
            meets = False
        if not meets:
            self.report_details["meets_requirements"] = False


if __name__ == "__main__":
    path = "project/"
    my_report = rep.Report(path)
    my_report.generate_report()
