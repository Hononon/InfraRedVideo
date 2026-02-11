import numpy as np
from scipy.optimize import fsolve

def planck(wl, T):
    """
    普朗克函数
    wl: 波长 (单位: m)
    T:  温度 (单位: K)
    返回: 光谱辐射亮度 (W·sr^-1·m^-3)
    """
    h = 6.626070e-34  # 普朗克常数
    c = 2.997925e8    # 光速
    k = 1.380649e-23  # 玻尔兹曼常数

    return ((2*h*c**2) / (wl**5)) * (1 / (np.exp((h*c) / (wl*k*T)) - 1))

def inverse_planck(wl, L, initial_guess=300):
    """
    通过已知辐射量计算温度
    wl: 波长 (单位: m)
    L:  光谱辐射亮度 (W·sr^-1·m^-3)
    initial_guess: 初始温度猜测值 (单位: K)，默认为300K
    返回: 计算得到的温度 (单位: K)
    """
    # 定义目标函数：我们希望planck(wl, T) = L，即planck(wl, T) - L = 0
    def objective(T):
        return planck(wl, T) - L
    
    # 使用fsolve求解非线性方程
    T_solution, = fsolve(objective, initial_guess)
    
    return T_solution