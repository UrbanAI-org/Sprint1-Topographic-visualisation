from time import sleep
from bs4 import BeautifulSoup
import requests
import re
import json

# Const
main_USGS="https://earthexplorer.usgs.gov/"
login = "https://ers.cr.usgs.gov/login"
save = "https://earthexplorer.usgs.gov/tabs/save"
search = "https://earthexplorer.usgs.gov/scene/search"
download_option = "https://earthexplorer.usgs.gov/scene/downloadoptions"
download = "https://earthexplorer.usgs.gov/download"

header={
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-AU,zh;q=0.9",
    "Connection": "keep-alive",
    "Host": "earthexplorer.usgs.gov",
    "sec-ch-ua": "\"Chromium\";v=\"110\", \"Not A(Brand\";v=\"24\", \"Microsoft Edge\";v=\"110\"",
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": "\"Windows\"",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36 Edg/110.0.1587.69"

}

DATASET_CODE = "5e83a3ee1af480c5"

# global variable
s = requests.Session()
# set requests headers
s.headers.update(header)

def load_cookies() -> bool:
    """
    tring to load cookies, if it doesn't exist or expired, return false. Otherwise, return true.
    """
    try:
        with open('cookie.txt', 'r') as f:
            cookies = requests.utils.cookiejar_from_dict(json.load(f))
            s.cookies.update(cookies)
        r = s.get(login, allow_redirects=False, headers={"Host": "ers.cr.usgs.gov"})
        if r.status_code == 302:
            print("cached cookies apply")
            return True
        print("cached cookies expired")
        s.cookies.clear()
        return False
    except FileNotFoundError:
        return False

def usgs_login(username: str, password: str) -> None:
    """
    Using username and password login into the USGS, 
    Save cookies if successfully logged in.
    If USGS found us to be a script, print the response and exit the program.
    """
    r = s.get(main_USGS)
    s.headers.update({"Host": "ers.cr.usgs.gov", "Sec-Fetch-Site": "same-origin"})
    if (load_cookies()):
        return
    print("to login page")
    r = s.get(login,headers={"Referer": main_USGS})
    html = BeautifulSoup(r.text, "html.parser")
    # read csrf token from html
    csrf_tag = html.find('input', {"type":"hidden", "name":"csrf"})
    csrf = None
    if csrf_tag is None:
        print(r.text)
        exit()
    else:
        csrf = csrf_tag['value']
    # print(csrf)
    payload = {
        "username": username,
        "password": password,
        "csrf": csrf
    }
    print("user login")
    # send login post request  
    sleep(0.5)
    r = s.post(login, 
        headers={"Referer": login, "Content-Type": "application/x-www-form-urlencoded", "Origin": main_USGS},
        data=payload,
        allow_redirects=False)
    # If there is EROS_SSO_production_secure in the cookies, it means that we have successfully logged in
    if 'EROS_SSO_production_secure' in s.cookies.get_dict().keys():
        # print(s.cookies.get_dict())
        print("successfully logged in")
        with open('cookie.txt', 'w') as f:
            json.dump(requests.utils.dict_from_cookiejar(s.cookies), f)
    else:
        print(r.text)
        exit()

def crawl_rows(entities : list, html : BeautifulSoup):
    """
    crawl entities information in result rows in given html
    """
    for tag in html.find_all("tr", {"id": re.compile("resultRow_.*?")}):
        attrs = tag.attrs
        # match attribute name of rows
        regexp_dei = re.compile(r'(?i)data-entityid')  # sometimes it is "data-entityId", "data-Entityid", ..... :)
        regexp_dci = re.compile(r'(?i)data-collectionid') # sometimes it is "data-collectionId" ................... 
        data_entityid = list(filter(regexp_dei.match, attrs.keys()))[0]
        data_collectionid = list(filter(regexp_dci.match, attrs.keys()))[0]
        # print(data_entityid, data_collectionid)
        try:
            entities.append({"data-entityId": attrs[data_entityid], "data-corner-points": attrs['data-corner-points'], "data-collectionid": attrs[data_collectionid]})
        except KeyError:
            # If there is any KeyError, save all information into our buffer.
            print(attrs)
            entities.append(attrs)
    pass

def search_by_coord(polygon : list) -> list:
    """
    given a list of coordinates, try to crawl all information. 
    Return a list that contain entities information that may be needed
    """
    s.headers.update({"Host": "earthexplorer.usgs.gov"})
    payload_coord = {
        "tab" : 1,
        "destination" : 2,
        "coordinates" : [],
        "format" : "dd",
        "dStart" : "",
        "dEnd": "",
        "searchType": "Std",
        "includeUnknownCC": "1",
        "maxCC": 100,
        "minCC" : 0,
        "months": ["","0","1","2","3","4","5","6","7","8","9","10","11"],
        "pType":"polygon"
    }
    count = 0
    # Translation coordinates format
    # (-33.9103, 151.2165) -> {"c": "0, 1, 2, ...", "a": "-33.9103", "o": "151.2165")}
    for coord in polygon:
        payload_coord['coordinates'].append({"c": f"{count}", "a" : f"{coord[0]}", "o" : f"{coord[1]}"})
        count += 1
    # update request header 
    s.headers.update(
        {
            "Sec-Fetch-Dest": "empty", 
            "Sec-Fetch-Mode": "cors", 
            "X-Requested-With": "XMLHttpRequest", 
            "Origin": "https://earthexplorer.usgs.gov", 
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8", 
            "Referer": "https://earthexplorer.usgs.gov/", 
            "Accept": "text/plain, */*; q=0.01"
        }
    )
    s.headers.pop("Sec-Fetch-User")

    print("Save")
    r = s.post(save, data={"data": json.dumps(payload_coord)})
    if r.status_code != 200:
        print(r.txt)
        exit()
    sleep(0.5)
    
    payload_dataset = {
        "tab": 2,
        "destination": 4,
        "cList":[DATASET_CODE],
        "selected": 0
    }
    print("Save")
    r = s.post(save, data={"data": json.dumps(payload_dataset)})
    sleep(0.5)

    entities = []
    if r.status_code != 200:
        print(r.text)
        exit()
    print("search")
    r = s.post(search,
            data={
                "datasetId": DATASET_CODE,
                "resultsPerPage": 10
            })
    if r.status_code != 200:
        print(r.text)
        exit()
    else:
        html = BeautifulSoup(r.text, "html.parser")
        pages = html.find("input", {"class" : "pageSelector"})
        if int(pages['max']) > 1:
            # TODO: CONTINUE CRAWL NEXT PAGE
            # r = s.post(search,
            # data={
            #     "datasetId": DATASET_CODE,
            #     "resultsPerPage": 10,
            #     "pageNum" : 2 # for example
            # })
            pass
        # Currently I'm assuming only one page is returned, just a demo
        crawl_rows(entities, html)
    return entities

def get_download_url(entities : list):
    """
    Get download options for all entities, try to get download link for Geotiff.

    """
    s.headers.update(
        {
            "Accept": "text/html, */*; q=0.01",
        }
    )
    s.headers.pop("Content-Type")
    print("get download options")
    # For each entity in our dataset, try to get the download option.
    for entity in entities:
        r = s.post(
            f"{download_option}/{entity['data-collectionid']}/{entity['data-entityId']}",
        )
        if r.status_code != 200:
            continue
        else:
            html = BeautifulSoup(r.text, "html.parser")
            regexp = re.compile(r'(?i)GeoTIFF')
            for tag in html.find_all("div", {"class" : "row downloadRow clearfix"}):
                button_div = tag.find("div", {"class": "downloadButtons"})
                name_div = tag.find("div", {"class": "name"})
                if regexp.search(name_div.string):
                    attr = button_div.contents[1].attrs
                    regexp_dpi = re.compile(r'(?i)data-productid')
                    data_entityid = list(filter(regexp_dpi.match, attr.keys()))[0]
                    try:
                        entity['data-productId'] = attr[data_entityid]
                    except KeyError:
                        entity.update(attr)
                        print(attr)
        sleep(0.5)
    s.headers.update(
        {
            "Accept": "application/json, text/javascript, */*; q=0.01"
        }
    )
    print("get download url")
    for entity in entities:
        r = s.post(
            f"{download}/{entity['data-productId']}/{entity['data-entityId']}/",
            allow_redirects=False
        )
        if r.status_code != 200:
            print(r.text)
            continue
        else:
            response = r.json()
            entity['url'] = response['url']
    pass

if __name__ == "__main__":
    USERNAME = "USERNAME"
    PASSWORD = "PASSWORD"
    usgs_login(USERNAME, PASSWORD)
    polygon = [
        (-33.1582, 150.3589),
        (-34.3276, 150.4880),
        (-33.9502, 152.0288)
    ]
    entities = search_by_coord(polygon)
    get_download_url(entities)
    print(entities)
    with open('data.json', 'w') as f:
        json.dump(entities, f)
