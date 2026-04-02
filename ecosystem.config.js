module.exports = {
  apps: [
    {
      name: 'machcore-api',
      script: 'node dist/src/main',
      cwd: '/home/karkyon/projects/machcore/apps/api',
      env: { NODE_ENV: 'production' },
    },
    {
      name: 'machcore-web',
      script: 'pnpm',
      args: 'run dev',
      cwd: '/home/karkyon/projects/machcore/apps/web',
      env: { NODE_ENV: 'development', PORT: '3010' },
    },
  ],
};
