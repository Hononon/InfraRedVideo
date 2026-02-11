import axios from 'axios'

// 自动根据前端访问地址推导后端地址：把 5173 端口替换成 5001
const defaultBase =
  typeof window !== 'undefined'
    ? window.location.origin.replace(':5173', ':5001')
    : 'http://localhost:5001'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_BASE || defaultBase,
  withCredentials: true,
})

