import numpy as np
import matplotlib.pyplot as plt

# 设置中文字体支持
plt.rcParams["font.family"] = ["SimHei", "WenQuanYi Micro Hei", "Heiti TC", "Times New Roman"]
plt.rcParams["axes.unicode_minus"] = False  # 正确显示负号

def plot_di_cl_data(file_path='d_i_cl.npy'):
    """加载并绘制d_i_cl.npy中的数据"""
    # 加载数据
    try:
        d_i_list = np.load(file_path)
        print(f"成功加载数据，数据形状: {d_i_list.shape}")
    except FileNotFoundError:
        print(f"错误: 未找到文件 {file_path}")
        return
    except Exception as e:
        print(f"加载数据时发生错误: {e}")
        return
    
    # 创建对应的CL值数组（与原代码保持一致的范围和步长）
    # 假设数据是按照CL从0到30000000，步长100生成的
    cl_values = np.arange(0, len(d_i_list)) * 100
    
    # 创建图形
    fig, ax = plt.subplots(figsize=(10, 6))
    
    # 绘制曲线
    ax.plot(cl_values / 100, d_i_list, color='blue', linewidth=1.5)
    
    # 设置坐标轴刻度在内侧
    ax.tick_params(direction='in', which='both')
    
    # 设置坐标轴标签
    ax.set_xlabel("CL /ppm-m", fontsize=14)
    ax.set_ylabel("ΔI /(10² W·m⁻²·sr⁻¹·Hz⁻¹)", fontsize=14)
    
    # 设置标题
    ax.set_title("CL与ΔI的关系曲线", fontsize=16)
    
    # 添加网格线
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # 调整布局
    plt.tight_layout()
    
    # 显示图形
    plt.show()
    
    return cl_values, d_i_list

if __name__ == '__main__':
    # 调用函数绘制图形，可指定文件路径
    cl, di = plot_di_cl_data('/mnt/video/2025-06-06-11-47-03.raw_d_i_cl.npy')
    
    # 可选：输出数据的基本统计信息
    print(f"数据长度: {len(di)}")
    print(f"ΔI最大值: {np.max(di):.6f}")
    print(f"ΔI最小值: {np.min(di):.6f}")
    print(f"ΔI平均值: {np.mean(di):.6f}")
