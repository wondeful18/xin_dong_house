import os
import sys
import subprocess
import re

def convert_txt_to_azw3(input_file):
    if not input_file.lower().endswith('.txt'):
        print(f"跳过非TXT文件: {input_file}")
        return

    base_name = os.path.splitext(os.path.basename(input_file))[0]
    # 中间先转一个临时 md 增加目录层级
    temp_md = "temp_novel.md"
    output_file = os.path.join(os.path.dirname(input_file), f"{base_name}.azw3")

    print(f"正在预处理章节目录...")
    
    # 预处理：识别“第X章”并加上 Markdown 标题符，确保 AZW3 有目录
    chapter_regex = re.compile(r'^\s*(第[一二三四五六七八九十百0-9]+[章节回])(.*)')
    
    with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
    
    with open(temp_md, 'w', encoding='utf-8') as f:
        for line in lines:
            clean_line = line.strip()
            if chapter_regex.match(clean_line):
                f.write(f"\n# {clean_line}\n\n") # 加上 # 变成一级标题
            else:
                f.write(line)

    print(f"正在调用 Calibre 引擎转换为 AZW3...")
    
    # 使用 Calibre 的命令行工具转换
    # --authors: 设置作者
    # --chapter: 自动识别标题
    # --page-breaks-before: 在章节前分页
    cmd = [
        'ebook-convert', 
        temp_md, 
        output_file, 
        '--authors', '汪文宇',
        '--title', base_name,
        '--chapter', "//*[name()='h1' or name()='h2']",
        '--page-breaks-before', "//*[name()='h1']",
        '--insert-blank-line', # 自动插入段间距，更适合阅读
        '--extra-css', "body { font-size: 1.2em; }" # 默认预设大一点的字体基准
    ]
    
    try:
        subprocess.run(cmd, check=True)
        print(f"--- 转换成功: {output_file} ---")
    except Exception as e:
        print(f"--- 转换失败: {e} ---")
    finally:
        if os.path.exists(temp_md):
            os.remove(temp_md)

if __name__ == "__main__":
    files = sys.argv[1:] if len(sys.argv) > 1 else [f for f in os.listdir('.') if f.endswith('.txt')]
    for f in files:
        convert_txt_to_azw3(f)