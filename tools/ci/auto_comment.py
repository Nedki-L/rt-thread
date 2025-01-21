import json
import os
import requests

# 获取环境变量
pr_files = os.getenv("PR_FILES", "").splitlines()
maintainers_file = './MAINTAINER.json'

# 错误处理：如果没有文件列表，则提前退出
if not pr_files:
    print("No modified files found, exiting.")
    exit(0)

# 加载 MAINTAINER.json 文件
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
    owners = []
    for maintainer in maintainers:
        # 只检查维护者路径是否与文件匹配
        if any(file.startswith(maintainer['path']) for file in files):
            # 如果匹配，将所有者添加到列表中
            owners.extend(maintainer['owner'].split(','))
    return owners

# 获取与修改文件匹配的所有者
owners = find_owners_for_file(pr_files, maintainers_data)

# 如果没有找到所有者，退出并打印信息
if not owners:
    print("No matching owners found for the modified files.")
    exit(0)

# 生成评论内容
comment = ""
for owner in owners:
    # 获取GitHub用户名，假设格式为 owner_name (github_id)
    try:
        github_id = owner.split('(')[1].split(')')[0].strip()
    except IndexError:
        print(f"Warning: Malformed owner entry: {owner}")
        continue

    # 查找该所有者对应的tag
    matching_maintainers = [maintainer for maintainer in maintainers_data if github_id in maintainer['owner']]
    if matching_maintainers:
        tag = matching_maintainers[0].get('tag', 'No tag')
    else:
        tag = 'No tag'

    # 构造评论
    comment += f"@{github_id} Tag: {tag} Please take a review of this tag "

# 移除评论中的换行符和额外的空格
comment = comment.replace('\n', ' ').strip()

# 输出生成的评论
print(f"Generated comment: {comment}")

# 使用环境文件传递评论内容
with open(os.getenv('GITHUB_ENV'), 'a') as env_file:
    env_file.write(f"COMMENT_BODY={comment}\n")
