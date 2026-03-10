import toast from "react-hot-toast";

export const useToast = () => ({
  success: (msg: string) => toast.success(msg, { duration: 3000 }),
  error: (msg: string) => toast.error(msg, { duration: 4000 }),
  info: (msg: string) => toast(msg, { duration: 3000 }),
  loading: (msg: string) => toast.loading(msg),
  dismiss: (id?: string) => toast.dismiss(id),
});

export { toast };
