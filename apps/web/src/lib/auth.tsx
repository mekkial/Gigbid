import { createContext, useContext, useState, ReactNode } from "react";
import { getToken, setToken } from "./client";

const Ctx = createContext<{ token: string | null; login: (t: string) => void; logout: () => void }>({ token: null, login: () => {}, logout: () => {} });
export const useAuth = () => useContext(Ctx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setT] = useState<string | null>(getToken());
  return (
    <Ctx.Provider value={{ token, login: (t) => { setToken(t); setT(t); }, logout: () => { setToken(null); setT(null); } }}>
      {children}
    </Ctx.Provider>
  );
}
