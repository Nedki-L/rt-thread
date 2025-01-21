import json
import os
import requests
import re
import time

# 获取环境变量
pr_number = os.getenv("PR_NUMBER")  # 从环境变量获取 PR 编号
github_repo = os.getenv("GITHUB_REPOSITORY")
token = os.getenv("GITHUB_TOKEN")

if not pr_number or not github_repo or not token:
    print("Error: PR_NUMBER, GITHUB_REPOSITORY or GITHUB_TOKEN is not set.")
    exit(1)

# 获取PR修改的所有文件
def get_modified_files(pr_number, github_repo, token):
    url = f"https://api.github.com/repos/{github_repo}/pulls/{pr_number}/files"
    headers = {"Authorization": f"Bearer {token}"}
    
    modified_files = []
    page = 1
    while True:
        response = requests.get(url, headers=headers, params={"page": page, "per_page": 100})
        if response.status_code != 200:
            print(f"Error: Unable to fetch modified files for PR #{pr_number}")
            print(f"Response: {response.status_code}, {response.text}")
            exit(1)
        
        files = response.json()
        if not files:
            break
        
        modified_files.extend([file['filename'] for file in files])
        page += 1
        
    return modified_files

# 加载 MAINTAINER.json 文件
maintainers_file = './MAINTAINER.json'
try:
    with open(maintainers_file, 'r') as file:
        maintainers_data = json.load(file)
except FileNotFoundError:
    print(f"Error: {maintainers_file} not found!")
    exit(1)
except json.JSONDecodeError as e:
    print(f"Error: Failed to decode {maintainers_file}, invalid JSON!")
    print(f"Details: {e}")
    exit(1)

# 定义匹配所有者的函数
def find_owners_for_file(files, maintainers):
    owners = {}
    for file in files:
        for maintainer in maintainers:
            # 确保路径匹配：维护者路径是文件路径的前缀
            if file.startswith(maintainer["path"].lstrip('/')):  # 去掉路径中的前导斜杠
                tag = maintainer["tag"]
                if tag not in owners:
                    owners[tag] = set()
                owners[tag].update(maintainer['owner'].split(','))
    return owners

# 获取修改文件
modified_files = get_modified_files(pr_number, github_repo, token)

# 如果没有修改文件，则退出
if not modified_files:
    print("No modified files found in the PR.")
    exit(0)

# 获取与修改文件匹配的所有者
owners = find_owners_for_file(modified_files, maintainers_data)

# 如果没有找到所有者，退出并打印信息
if not owners:
    print("No matching owners found for the modified files.")
    exit(0)

# 提取评论格式化的所有者名字（仅提取github id部分）
def extract_owner_name(owner):
    match = re.match(r'.*\(([^)]+)\).*', owner)
    return match.group(1).strip() if match else owner.strip()

# 获取当前 PR 的所有评论
def get_existing_comments(pr_number, github_repo, token):
    response = requests.get(
        f"https://api.github.com/repos/{github_repo}/issues/{pr_number}/comments",
        headers={"Authorization": f"Bearer {token}"}
    )

    if response.status_code != 200:
        print(f"Error: Unable to fetch comments for PR #{pr_number}")
        print(f"Response: {response.status_code}, {response.text}")
        exit(1)

    return response.json()

existing_comments = get_existing_comments(pr_number, github_repo, token)

# 提取现有评论中的维护者
mentioned_owners = set()
for comment_data in existing_comments:
    if 'body' in comment_data:
        mentioned_owners.update(
            word.strip('@') for word in comment_data['body'].split() if word.startswith('@')
        )

# 根据未提及的维护者生成评论
comments_dir = "/tmp/comments"
os.makedirs(comments_dir, exist_ok=True)

# 用于追踪已提及的维护者
all_mentioned_owners = set()
# 用于追踪已处理的标签
processed_tags = set()

# 按顺序处理每个标签
for tag, owners_list in owners.items():
    if tag in processed_tags:
        continue  # 如果该标签已处理过，跳过

    # 提取当前标签的所有者，并去除已提及的维护者
    owners_set = {extract_owner_name(owner) for owner in owners_list}
    new_owners = owners_set - mentioned_owners

    # 更新全局的已提及维护者集合
    all_mentioned_owners.update(new_owners)

    # 生成评论时，确保每个维护者前面加上 `@` 符号
    if new_owners:
        # 获取当前时间戳
        current_time = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())

        # 创建评论内容
        comment_body = f"Timeout: {current_time}\n"
        comment_body += f"Reviewer: {' @'.join(sorted(all_mentioned_owners))}\n"  # 确保每个维护者加上 @
        comment_body += f"\nTag: {tag}\nPlease take a review of this tag\n"
        
        # 转义换行符和双引号
        comment_body = comment_body.replace('\n', '\\n').replace('"', '\\"')

        # 写入评论文件
        comment_file_path = f"{comments_dir}/{tag.replace(' ', '_')}_comment.txt"
        with open(comment_file_path, 'w') as f:
            f.write(comment_body)

        # 标记该标签已处理
        processed_tags.add(tag)

print(f"Comments generated in: {comments_dir}")
