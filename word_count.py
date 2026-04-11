import os
import re

# 配置信息（需与拆分脚本一致）
output_dir = "."

def count_chinese_chars(text):
    # 使用正则匹配所有中文字符（范围：\u4e00-\u9fa5）
    # 这样可以排除掉 YAML 头部、空格、数字和英文标点
    chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text)
    return len(chinese_chars)

def stat_novel_word_count(base_dir):
    total_words = 0
    print(f"{'章节':<15} | {'汉字数':<10}")
    print("-" * 30)

    # 获取所有卷目录并排序
    volumes = sorted([v for v in os.listdir(base_dir) if os.path.isdir(os.path.join(base_dir, v))])

    for vol in volumes:
        vol_path = os.path.join(base_dir, vol)
        print(f"\n【{vol}】")
        
        # 获取该卷下所有章节文件并排序
        chapters = sorted([c for c in os.listdir(vol_path) if c.endswith('.md')])
        
        for ch in chapters:
            ch_path = os.path.join(vol_path, ch)
            with open(ch_path, 'r', encoding='utf-8') as f:
                content = f.read()
                
                # 剔除 YAML Front Matter 干扰，只统计正文
                # 逻辑：如果存在 ---，则只取第二个 --- 之后的内容
                body = content
                if content.startswith('---'):
                    parts = content.split('---', 2)
                    if len(parts) >= 3:
                        body = parts[2]
                
                count = count_chinese_chars(body)
                total_words += count
                print(f"{ch:<15} | {count:<10}")

    print("-" * 30)
    print(f"全书总汉字数: {total_words}")

if __name__ == "__main__":
    if os.path.exists(output_dir):
        stat_novel_word_count(output_dir)
    else:
        print(f"错误：未找到目录 {output_dir}")