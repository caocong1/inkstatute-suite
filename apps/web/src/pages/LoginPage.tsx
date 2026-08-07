/** Placeholder — full implementation in Task 93-01-05 */
import { type Component } from "solid-js";
import { useAuth } from "../contexts/AuthContext";
import { useNavigate } from "@solidjs/router";

export const LoginPage: Component = () => {
  const auth = useAuth();
  const navigate = useNavigate();
  return <div>登录页面占位</div>;
};
