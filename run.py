
import os
import shutil
import re
import yaml

DIR_NAME="md-docs"

def print_color(text: str, color: str):
    if color == 'green':
        print(f"\033[32m{text}\033[0m")
    elif color == 'red':
        print(f"\033[31m{text}\033[0m")
    elif color == 'yellow':
        print(f"\033[33m{text}\033[0m")
    else:
        print(text)

class Paper:
    def __init__(self, path: str) -> None:
        self.path = path
        self.base_name = os.path.basename(path)[:-3]

        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # match content
        # - 题目: 
        # - 会议: 
        # - 视频: 
        # - 代码: 
        pattern = r"- 题目: (.*?)\n- 会议: (.*?)\n- 视频: (.*?)\n- 代码: (.*?)\n"
        match = re.search(pattern, content)
        if match:
            self.title = match.group(1)
            self.meeting = match.group(2)
            self.video = match.group(3)
            self.code = match.group(4)
            # print(f"title: {self.title}")
            # print(f"meeting: {self.meeting}")
            # print(f"video: {self.video}")
            # print(f"code: {self.code}")
            
            # if matched <!-- TODO --> means the paper hasn't been finished
            if "<!-- TODO -->" in content:
                self.is_matched = False
                print_color(f"not finished reading {self.base_name}, do it, hurry!", "yellow")
            else:
                self.is_matched = True
                print_color(f"finished reading {self.base_name}, good job!", "green")
        else:
            self.title = ""
            self.meeting = ""
            self.video = ""
            self.code = ""
            print_color(f"failed reading {self.base_name}, what are you waiting for?", "red")
            self.is_matched = False
            

def create_table(filename, papers: list[Paper]):
    
    with open(filename, "r", encoding="utf-8") as f:
        content = f.read()
        
    # find insert place between <!-- insert --> and <!-- end -->
    # <!-- insert -->
    # here
    # <!-- end -->
    insert_place = content.find("<!-- insert -->")
    if insert_place == -1:
        print("No insert place found in", filename)
        return
    end_place = content.find("<!-- end -->")
    if end_place == -1:
        print("No end place found in", filename)
        return
    
    # create markdown table
    
    # |paper|short_name|code|
    # |:--:|:--:|:--|
    # ||||
    table = "|paper|short_name|code|\n|:--:|:--:|:--:|\n"
    for paper in papers:
        if not paper.is_matched:
            continue
        table += f"|{paper.title}|{paper.base_name}|{paper.code}|\n"
    
    # insert table
    # include insert place and end place source text
    new_content = content[:insert_place] + "<!-- insert -->\n" + table + content[end_place:]
    # print(new_content)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(new_content)

def main():
    
    papers = []
    excluse_md_names = ['README', 'template']
    
    # find all md files in dir.yml
    # .:
    # - README: 1
    # - tpp: 2
    # - vtmm: 3
    # - memtis: 4
    # - hugegpt: 5
    # - hemem: 6
    # - nimble: 7
    # - mitosis: 8
    # - thermostat: 9
    # - telescope: 10
    # - mtm: 11
    # - nomad: 12
    # - autotiering: 13
    # - hydra: 14
    dir_yaml = os.path.join(DIR_NAME, "dir.yml")
    with open(dir_yaml, "r", encoding="utf-8") as f:
        dir_yaml_content = f.read()
    
    dir_yaml_content = yaml.load(dir_yaml_content, Loader=yaml.FullLoader)
    # print(dir_yaml_content["."])
    # [{'README': 1}, {'tpp': 2}, {'vtmm': 3}, {'memtis': 4}, {'hugegpt': 5}, {'hemem': 6}, {'nimble': 7}, {'mitosis': 8}, {'thermostat': 9}, {'telescope': 10}, {'mtm': 11}, {'nomad': 12}, {'autotiering': 13}, {'hydra': 14}]
    for item in dir_yaml_content["."]:
        for paper_name in item:
            if paper_name in excluse_md_names:
                continue
            path = os.path.join(DIR_NAME, paper_name + ".md")
            papers.append(Paper(path))
    
    create_table(os.path.join(DIR_NAME, "README.md"), papers)
    create_table("README.md", papers)
    
if __name__ == "__main__":
    main()