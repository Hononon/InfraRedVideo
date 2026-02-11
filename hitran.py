import numpy as np
import matplotlib.pyplot as plt

def planck(wl, t):
    """Planck 辐射定律"""
    h = 6.626070e-34
    c = 2.997925e8
    k = 1.380649e-23
    return ((2*h*(c**2))/(wl**5)) * (1/(np.exp((h*c)/(wl*k*t))-1))

def f_filter_vectorized(x):
    """多项式滤波函数（向量化版本）"""
    result = x * 1434.81195 + (x ** 2) * (-406.65706) + (x ** 3) * 38.24031 - 1679.70048
    return np.where(result >= 0.82, 0.82, result)

def delta_i_vectorized_CLs(Tb, Tg, CLs, nu, coef):
    """计算 ΔI 对应的 CL 数组"""
    rf_values = 1 - np.exp(-coef * 1e-6 * CLs[:, np.newaxis])
    rf_filtered = np.minimum(rf_values, f_filter_vectorized(nu))
    deltas = planck(nu * 1e-6, Tb) - planck(nu * 1e-6, Tg)
    nu_diff = np.diff(nu) * 1e-6
    return np.sum(deltas[:-1] * rf_filtered[:, :-1] * nu_diff, axis=1)

def generate_d_i_cl(Tb, Tg, ch4_coef_path, output_path, cl_max=300000, cl_step=100):
    """
    生成 d_i_cl.npy 查找表
    Tb: 背景温度 (K)
    Tg: 气体温度 (K)
    ch4_coef_path: CH4_nu_coef.npy 路径
    output_path: 输出文件路径
    cl_max: 最大 CL 值 (ppm-m)
    cl_step: CL 步长
    """
    # 读取 nu 和 coef
    CH4_nu_coef = np.load(ch4_coef_path)
    nu = (1 / CH4_nu_coef[0, :]) * 10000  # 转换波长
    coef = CH4_nu_coef[1, :]

    # 翻转数组，保证从大到小
    nu, coef = nu[::-1], coef[::-1]

    # 生成 CL 数组
    CLs = np.arange(0, cl_max, 100) * cl_step

    # 计算 ΔI
    d_i_list = delta_i_vectorized_CLs(Tb, Tg, CLs, nu, coef)

    # 保存结果
    np.save(output_path, d_i_list)
    print(f"查找表已保存到 {output_path}，数组形状: {d_i_list.shape}")

    return CLs, d_i_list


    # 示例调用
    # Tb = 317.55  # 背景温度 K
    # Tg = 313.15  # 气体温度 K
    # ch4_coef_path = "./CH4_nu_coef.npy"
    # output_path = "d_i_cl.npy"
    #
    # CLs, d_i_list = generate_d_i_cl(Tb, Tg, ch4_coef_path, output_path)
    #
    # # 可选：绘制曲线
    # plt.plot(CLs / 100, d_i_list)
    # plt.xlabel("CL / ppm-m", fontfamily="Times New Roman", fontsize=14)
    # plt.ylabel("${\Delta}$I /(10$^2$ W·m$^-$$^2$·sr$^-$$^1$·Hz$^-$$^1$)",
    #            fontfamily="Times New Roman", fontsize=14)
    # plt.show()