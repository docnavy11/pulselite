import { create } from 'zustand';
import { getDeploymentConfig } from '@/lib/api-functions';

interface DeploymentState {
  isCloud: boolean;
  isLoaded: boolean;
  loadConfig: () => Promise<void>;
}

export const useDeploymentStore = create<DeploymentState>((set) => ({
  isCloud: false,
  isLoaded: false,
  loadConfig: async () => {
    try {
      const config = await getDeploymentConfig();
      set({ isCloud: config.cloud_mode, isLoaded: true });
    } catch {
      set({ isCloud: false, isLoaded: true });
    }
  },
}));
