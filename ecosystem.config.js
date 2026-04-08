module.exports = {
  apps: [
    {
      name:    'machcore-api',
      script:  'dist/main.js',
      cwd:     '/home/karkyon/projects/machcore/apps/api',
      instances: 1,
      autorestart: true,
      watch:   false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        API_PORT: 3011,
      },
      error_file:      '/home/karkyon/.pm2/logs/machcore-api-error.log',
      out_file:        '/home/karkyon/.pm2/logs/machcore-api-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
    {
      name:    'machcore-web',
      script:  'node_modules/.bin/next',
      args:    'start -p 3010 -H 0.0.0.0',
      cwd:     '/home/karkyon/projects/machcore/apps/web',
      instances: 1,
      autorestart: true,
      watch:   false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        PORT:     3010,
      },
      error_file:      '/home/karkyon/.pm2/logs/machcore-web-error.log',
      out_file:        '/home/karkyon/.pm2/logs/machcore-web-out.log',
      log_date_format: 'YYYY-MM-DD HH:mm:ss',
    },
  ],
};
