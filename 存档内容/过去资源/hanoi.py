import json
import os

# ==================== 全局参数配置 ====================
# 汉诺塔层数 (7层最小步数为 2^7 - 1 = 127 步)
HANOI_LAYERS = 7

# 三个柱子的屏幕绝对坐标 (X, Y)
# 默认基准: 1920x1080 分辨率屏幕中心 (960, 540)
CENTER_X = 960
CENTER_Y = 540
OFFSET = 280  # 偏移量

LEFT_PILLAR = (CENTER_X - OFFSET, CENTER_Y)   # 中心偏左280像素
MIDDLE_PILLAR = (CENTER_X, CENTER_Y)          # 屏幕中心
RIGHT_PILLAR = (CENTER_X + OFFSET, CENTER_Y)  # 中心偏右280像素

# 延迟参数配置
MOUSE_MOVE_DURATION = 5  # move_to 鼠标移动总时长 (毫秒)
CLICK_FRAME_DELAY = "1f"  # 鼠标点击(md/mu)的帧延迟 (1帧)

# 输出文件配置
OUTPUT_DIR = "宏"
OUTPUT_FILENAME = "汉诺塔_7层.json"
# =====================================================

def hanoi(n, source, target, auxiliary, moves):
    """
    递归计算汉诺塔的最小步数移动路径
    :param n: 层数
    :param source: 源柱子坐标
    :param target: 目标柱子坐标
    :param auxiliary: 辅助柱子坐标
    :param moves: 记录步骤的列表
    """
    if n == 1:
        moves.append((source, target))
    else:
        # 将 n-1 层从源柱子移动到辅助柱子
        hanoi(n - 1, source, auxiliary, target, moves)
        # 将最底下的第 n 层从源柱子移动到目标柱子
        moves.append((source, target))
        # 将 n-1 层从辅助柱子移动到目标柱子
        hanoi(n - 1, auxiliary, target, source, moves)

def generate_macro(moves):
    """
    根据移动步骤生成符合框架要求的 JSON 宏指令列表
    单次移动 = 移动到源柱 -> 点击拿起 -> 移动到目标柱 -> 点击放下
    """
    macro_commands = []
    
    for src, tgt in moves:
        src_x, src_y = src
        tgt_x, tgt_y = tgt
        
        # 1. 鼠标移动到源柱子位置
        macro_commands.append(["move_to", src_x, src_y, MOUSE_MOVE_DURATION])
        
        # 2. 鼠标左键按下 (等待1帧)
        macro_commands.append(["md", "left", CLICK_FRAME_DELAY])
        # 3. 鼠标左键抬起 (等待1帧) —— 至此完成"拿起"
        macro_commands.append(["mu", "left", CLICK_FRAME_DELAY])
        
        # 4. 鼠标移动到目标柱子位置
        macro_commands.append(["move_to", tgt_x, tgt_y, MOUSE_MOVE_DURATION])
        
        # 5. 鼠标左键按下 (等待1帧)
        macro_commands.append(["md", "left", CLICK_FRAME_DELAY])
        # 6. 鼠标左键抬起 (等待1帧) —— 至此完成"放下"
        macro_commands.append(["mu", "left", CLICK_FRAME_DELAY])
        
    return macro_commands

def main():
    print(f"正在计算 {HANOI_LAYERS} 层汉诺塔最优步骤...")
    moves = []
    # 从左侧柱子移动到右侧柱子，中间柱子作为辅助
    hanoi(HANOI_LAYERS, LEFT_PILLAR, RIGHT_PILLAR, MIDDLE_PILLAR, moves)
    
    total_steps = len(moves)
    print(f"计算完成，共需 {total_steps} 步移动。")
    
    print("正在生成宏指令...")
    macro_data = generate_macro(moves)
    
    # 确保输出目录存在
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        
    output_path = os.path.join(OUTPUT_DIR, OUTPUT_FILENAME)
    
    print(f"正在写入宏文件: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        # ensure_ascii=False 防止中文路径转义，indent=2 使文件结构易于阅读
        json.dump(macro_data, f, ensure_ascii=False, indent=2)
        
    print("生成完成！请将该 JSON 文件放入宏执行框架的对应目录并绑定按键使用。")

if __name__ == "__main__":
    main()
