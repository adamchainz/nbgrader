import pytest
import os
import time

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

from .. import run_nbgrader
from .conftest import notwindows


def _wait(browser):
    return WebDriverWait(browser, 10)


def _load_assignments_list(browser, port, retries=5):
    # go to the correct page
    browser.get("http://localhost:{}/tree".format(port))

    def page_loaded(browser):
        return browser.execute_script(
            'return typeof IPython !== "undefined" && IPython.page !== undefined;')

    # wait for the page to load
    try:
        _wait(browser).until(page_loaded)
    except TimeoutException:
        if retries > 0:
            print("Retrying page load...")
            # page timeout, but sometimes this happens, so try refreshing?
            _load_assignments_list(browser, port, retries=retries - 1)
        else:
            print("Failed to load the page too many times")
            raise

    # wait for the extension to load
    _wait(browser).until(EC.presence_of_element_located((By.CSS_SELECTOR, "#assignments")))

    # switch to the assignments list
    element = browser.find_element_by_link_text("Assignments")
    element.click()

    # make sure released, downloaded, and submitted assignments are visible
    _wait(browser).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#released_assignments_list")))
    _wait(browser).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#fetched_assignments_list")))
    _wait(browser).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#submitted_assignments_list")))


def _expand(browser, list_id, assignment):
    browser.find_element_by_link_text(assignment).click()
    rows = browser.find_elements_by_css_selector("{} .list_item".format(list_id))
    for i in range(1, len(rows)):
        _wait(browser).until(lambda browser: browser.find_elements_by_css_selector("{} .list_item".format(list_id))[i].is_displayed())
    return rows


def _unexpand(browser, list_id, assignment):
    browser.find_element_by_link_text(assignment).click()
    rows = browser.find_elements_by_css_selector("{} .list_item".format(list_id))
    for i in range(1, len(rows)):
        _wait(browser).until(lambda browser: not browser.find_elements_by_css_selector("{} .list_item".format(list_id))[i].is_displayed())


def _wait_for_modal(browser):
    _wait(browser).until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, ".modal-dialog")))


def _dismiss_modal(browser):
    button = browser.find_element_by_css_selector(".modal-footer .btn-primary")
    button.click()

    def modal_gone(browser):
        try:
            browser.find_element_by_css_selector(".modal-dialog")
        except NoSuchElementException:
            return True
        return False
    _wait(browser).until(modal_gone)


def _sort_rows(x):
    try:
        item_name = x.find_element_by_class_name("item_name").text
    except NoSuchElementException:
        item_name = ""
    return item_name


def _wait_until_loaded(browser):
    _wait(browser).until(lambda browser: browser.find_element_by_css_selector("#course_list_dropdown").is_enabled())


def _change_course(browser, course):
    # wait until the dropdown is enabled
    _wait_until_loaded(browser)

    # click the dropdown to show the menu
    dropdown = browser.find_element_by_css_selector("#course_list_dropdown")
    dropdown.click()

    # parse the list of courses and click the one that's been requested
    courses = browser.find_elements_by_css_selector("#course_list > li")
    text = [x.text for x in courses]
    index = text.index(course)
    courses[index].click()

    # wait for the dropdown to be disabled, then enabled again
    _wait_until_loaded(browser)

    # verify the dropdown shows the correct course
    default = browser.find_element_by_css_selector("#course_list_default")
    assert default.text == course


def _wait_for_list(browser, name, num_rows):
    _wait(browser).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "#{}_assignments_list_loading".format(name))))
    _wait(browser).until(EC.invisibility_of_element_located((By.CSS_SELECTOR, "#{}_assignments_list_placeholder".format(name))))
    _wait(browser).until(lambda browser: len(browser.find_elements_by_css_selector("#{}_assignments_list > .list_item".format(name))) == num_rows)
    rows = browser.find_elements_by_css_selector("#{}_assignments_list > .list_item".format(name))
    assert len(rows) == num_rows
    return rows


@pytest.mark.nbextensions
@notwindows
def test_show_assignments_list(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # make sure all the placeholders are initially showing
    _wait(browser).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#released_assignments_list_placeholder")))
    _wait(browser).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#fetched_assignments_list_placeholder")))
    _wait(browser).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#submitted_assignments_list_placeholder")))

    # release an assignment
    run_nbgrader(["assign", "Problem Set 1"])
    run_nbgrader(["release", "Problem Set 1", "--course", "abc101"])

    # click the refresh button
    browser.find_element_by_css_selector("#refresh_assignments_list").click()
    _wait_until_loaded(browser)

    # wait for the released assignments to update
    rows = _wait_for_list(browser, "released", 1)
    assert rows[0].find_element_by_class_name("item_name").text == "Problem Set 1"
    assert rows[0].find_element_by_class_name("item_course").text == "abc101"


@pytest.mark.nbextensions
@notwindows
def test_multiple_released_assignments(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # release another assignment
    run_nbgrader(["assign", "ps.01"])
    run_nbgrader(["release", "ps.01", "--course", "xyz 200"])

    # click the refresh button
    browser.find_element_by_css_selector("#refresh_assignments_list").click()
    _wait_until_loaded(browser)

    # choose the course "xyz 200"
    _change_course(browser, "xyz 200")

    rows = _wait_for_list(browser, "released", 1)
    assert rows[0].find_element_by_class_name("item_name").text == "ps.01"
    assert rows[0].find_element_by_class_name("item_course").text == "xyz 200"


@pytest.mark.nbextensions
@notwindows
def test_fetch_assignment(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # choose the course "xyz 200"
    _change_course(browser, "xyz 200")

    # click the "fetch" button
    rows = _wait_for_list(browser, "released", 1)
    rows[0].find_element_by_css_selector(".item_status button").click()

    # wait for the downloaded assignments list to update
    rows = _wait_for_list(browser, "fetched", 1)
    assert rows[0].find_element_by_class_name("item_name").text == "ps.01"
    assert rows[0].find_element_by_class_name("item_course").text == "xyz 200"
    assert os.path.exists(os.path.join(tempdir, "ps.01"))

    # expand the assignment to show the notebooks
    rows = _expand(browser, "#nbgrader-xyz_200-ps01", "ps.01")
    rows.sort(key=_sort_rows)
    assert len(rows) == 2
    assert rows[1].find_element_by_class_name("item_name").text == "problem 1"

    # unexpand the assignment
    _unexpand(browser, "#nbgrader-xyz_200-ps01", "ps.01")


@pytest.mark.nbextensions
@notwindows
def test_submit_assignment(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # choose the course "xyz 200"
    _change_course(browser, "xyz 200")

    # submit it
    rows = _wait_for_list(browser, "fetched", 1)
    rows[0].find_element_by_css_selector(".item_status button").click()

    # wait for the submitted assignments list to update
    rows = _wait_for_list(browser, "submitted", 1)
    assert rows[0].find_element_by_class_name("item_name").text == "ps.01"
    assert rows[0].find_element_by_class_name("item_course").text == "xyz 200"

    # submit it again
    rows = browser.find_elements_by_css_selector("#fetched_assignments_list > .list_item")
    rows[0].find_element_by_css_selector(".item_status button").click()

    # wait for the submitted assignments list to update
    rows = _wait_for_list(browser, "submitted", 2)
    rows.sort(key=_sort_rows)
    assert rows[0].find_element_by_class_name("item_name").text == "ps.01"
    assert rows[0].find_element_by_class_name("item_course").text == "xyz 200"
    assert rows[1].find_element_by_class_name("item_name").text == "ps.01"
    assert rows[1].find_element_by_class_name("item_course").text == "xyz 200"
    assert rows[0].find_element_by_class_name("item_status").text != rows[1].find_element_by_class_name("item_status").text


@pytest.mark.nbextensions
@notwindows
def test_fetch_second_assignment(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # click the "fetch" button
    rows = _wait_for_list(browser, "released", 1)
    rows[0].find_element_by_css_selector(".item_status button").click()

    # wait for the downloaded assignments list to update
    rows = _wait_for_list(browser, "fetched", 1)
    rows.sort(key=_sort_rows)
    assert rows[0].find_element_by_class_name("item_name").text == "Problem Set 1"
    assert rows[0].find_element_by_class_name("item_course").text == "abc101"
    assert os.path.exists(os.path.join(tempdir, "Problem Set 1"))

    # expand the assignment to show the notebooks
    rows = _expand(browser, "#nbgrader-abc101-Problem_Set_1", "Problem Set 1")
    rows.sort(key=_sort_rows)
    assert len(rows) == 3
    assert rows[1].find_element_by_class_name("item_name").text == "Problem 1"
    assert rows[2].find_element_by_class_name("item_name").text == "Problem 2"

    # unexpand the assignment
    _unexpand(browser, "abc101-Problem_Set_1", "Problem Set 1")


@pytest.mark.nbextensions
@notwindows
def test_submit_other_assignment(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # submit it
    rows = _wait_for_list(browser, "fetched", 1)
    rows[0].find_element_by_css_selector(".item_status button").click()

    # wait for the submitted assignments list to update
    rows = _wait_for_list(browser, "submitted", 1)
    rows.sort(key=_sort_rows)
    assert rows[0].find_element_by_class_name("item_name").text == "Problem Set 1"
    assert rows[0].find_element_by_class_name("item_course").text == "abc101"


@pytest.mark.nbextensions
@notwindows
def test_validate_ok(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # choose the course "xyz 200"
    _change_course(browser, "xyz 200")

    # expand the assignment to show the notebooks
    _wait_for_list(browser, "fetched", 1)
    rows = _expand(browser, "#nbgrader-xyz_200-ps01", "ps.01")
    rows.sort(key=_sort_rows)
    assert len(rows) == 2
    assert rows[1].find_element_by_class_name("item_name").text == "problem 1"

    # click the "validate" button
    rows[1].find_element_by_css_selector(".item_status button").click()

    # wait for the modal dialog to appear
    _wait_for_modal(browser)

    # check that it succeeded
    browser.find_element_by_css_selector(".modal-dialog .validation-success")

    # close the modal dialog
    _dismiss_modal(browser)


@pytest.mark.nbextensions
@notwindows
def test_validate_failure(browser, port, class_files, tempdir):
    _load_assignments_list(browser, port)
    _wait_until_loaded(browser)

    # expand the assignment to show the notebooks
    _wait_for_list(browser, "fetched", 1)
    rows = _expand(browser, "#nbgrader-abc101-Problem_Set_1", "Problem Set 1")
    rows.sort(key=_sort_rows)
    assert len(rows) == 3
    assert rows[1].find_element_by_class_name("item_name").text == "Problem 1"
    assert rows[2].find_element_by_class_name("item_name").text == "Problem 2"

    # click the "validate" button
    rows[2].find_element_by_css_selector(".item_status button").click()

    # wait for the modal dialog to appear
    _wait_for_modal(browser)

    # check that it succeeded
    browser.find_element_by_css_selector(".modal-dialog .validation-failed")

    # close the modal dialog
    _dismiss_modal(browser)

