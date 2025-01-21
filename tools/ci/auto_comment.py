import json
import os
import requests
import re
import base64

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
    owners = {}
    for maintainer in maintainers:
        # 通过正则表达式检查文件路径是否匹配
        for file in files:
            if re.match(f'^{maintainer["path"]}', file):
                if maintainer['tag'] not in owners:
                    owners[maintainer['tag']] = []
                owners[maintainer['tag']].extend(maintainer['owner'].split(','))
    return owners

# 获取与修改文件匹配的所有者
owners = find_owners_for_file(pr_files, maintainers_data)

# 如果没有找到所有者，退出并打印信息
if not owners:
    print("No matching owners found for the modified files.")
    exit(0)

# 改进所有者信息提取
def extract_owner_name(owner):
    # 优化提取所有者的格式
    match = re.match(r'.*\(([^)]+)\).*', owner)
    if match:
        return match.group(1).strip()
    return owner.strip()  # 默认返回整个名字（如果没有符合的格式）

# 生成评论内容
comment = ""
new_owners = set()
for tag, owners_list in owners.items():
    owners_set = set(extract_owner_name(owner) for owner in owners_list)
    new_owners.update(owners_set)

    # 格式化评论，符合要求的格式
    reviewer_line = f"**:technologist: Reviewer:** {' '.join([f'@{owner}' for owner in owners_set])}"
    tag_line = f"**:label: Tag:** {tag}"
    review_focus = """
**:zap: Review Focus:**
The {tag} tag is ready for your review! Please pay close attention to the following aspects:
- **:dizzy: Logical Flow:** Ensure that the workflow follows a logical sequence that makes sense to users.
- **:mag: Optimizations:** Identify any opportunities to streamline the process for better efficiency.
- **:monocle_face: Test Coverage:** Check if the workflow addresses all possible edge cases.

**:speech_balloon: Collaboration:** Your review will significantly improve this workflow. Your feedback is crucial to ensure it’s as smooth and reliable as possible!

**:memo: Your Insight:**
Your thorough review will help us ensure this tag is perfect and ready for use by the team. Every suggestion you make will have a big impact on improving the overall workflow.
"""

    # 填充模板
    comment += f"{reviewer_line}\n{tag_line}\n{review_focus}\n\n"

# 移除评论中的换行符和额外的空格
comment = comment.strip()

# 打印生成的评论内容，调试输出
print(f"Generated comment: {comment}")

# 如果没有生成评论内容，退出并打印信息
if not comment:
    print("No comment generated. Exiting.")
    exit(1)

# 确保 COMMENT_BODY 被正确传递到环境变量
comment_file = '/tmp/comment_body.txt'
encoded_comment = base64.b64encode(comment.encode('utf-8')).decode('utf-8')  # 编码为 base64
with open(comment_file, 'w') as f:
    f.write(encoded_comment)

print(f"Comment written to: {comment_file}")

# 获取当前 PR 的评论
pr_number = os.getenv("PR_NUMBER")
response = requests.get(
    f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/issues/{pr_number}/comments",
    headers={"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}"}
)

# 打印API返回的数据，以便调试
print("Response from GitHub API:", response.json())

# 获取现有评论的 ID 和内容
existing_comments = response.json()
existing_comment_body = ""
existing_comment_id = None
for comment_data in existing_comments:
    if isinstance(comment_data, dict) and 'body' in comment_data:  # 检查是否为字典并包含body字段
        if "CI Reviewer" in comment_data['body']:  # 假设评论包含特定标识
            existing_comment_body = comment_data['body']
            existing_comment_id = comment_data['id']
            break

# 逻辑判断：是否需要新增评论
if existing_comment_body:
    # 比较当前评论与已有评论的差异，决定是否更新或新增
    existing_owners = set(word.strip('@') for word in existing_comment_body.split() if word.startswith('@'))
    if not new_owners.issubset(existing_owners):
        # 如果新维护者不是现有评论的一部分，新增评论
        print("Adding new comment with new maintainers.")
        requests.post(
            f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/issues/{pr_number}/comments",
            headers={"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}", "Content-Type": "application/json"},
            json={"body": comment}
        )
else:
    # 如果没有找到现有评论，则添加新评论
    print("Adding new comment.")
    requests.post(
        f"https://api.github.com/repos/{os.getenv('GITHUB_REPOSITORY')}/issues/{pr_number}/comments",
        headers={"Authorization": f"Bearer {os.getenv('GITHUB_TOKEN')}", "Content-Type": "application/json"},
        json={"body": comment}
    )
