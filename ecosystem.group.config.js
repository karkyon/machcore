// グループ会社インスタンス用 PM2 設定。
// 自社インスタンス（ecosystem.config.js）とはポート・cwd・DBを完全に分離する。
// 起動: pm2 start ecosystem.group.config.js
// 再起動: pm2 restart ecosystem.group.config.js --update-env
module.exports = {
  apps: [
    {
      name:    'machcore-group-api',
      script:  'dist/src/main.js',
      cwd:     '/home/karkyon/projects/machcore-group/apps/api',
      exec_mode: 'fork',
      instances: 1,
      autorestart: true,
      watch:   false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        API_PORT: 3021,
        TZ: 'Asia/Tokyo',
        // RIDOC_API_URL: 自社と同じ外部システムを使うか要確認。使わない場合は削除。
        RIDOC_API_URL: 'http://192.168.1.207:5087',
        CORS_ORIGINS: 'https://192.168.1.14:8543,http://localhost:3020,http://localhost:3021,http://192.168.1.14:3020',
      },
      error_file: '/home/karkyon/.pm2/logs/machcore-group-api-error.log',
      out_file:   '/home/karkyon/.pm2/logs/machcore-group-api-out.log',
    },
    {
      name:        'machcore-group-web',
      script:      '/home/karkyon/projects/machcore-group/start-web-group.sh',
      interpreter: '/bin/bash',
      exec_mode:   'fork',
      instances:   1,
      autorestart: true,
      watch:       false,
      max_memory_restart: '512M',
      env: {
        NODE_ENV: 'production',
        PORT: 3020,
        API_PORT: 3021,
        NEXT_ALLOWED_ORIGINS: '192.168.1.14,https://192.168.1.14:8543',
        TZ: 'Asia/Tokyo',
      },
      error_file: '/home/karkyon/.pm2/logs/machcore-group-web-error.log',
      out_file:   '/home/karkyon/.pm2/logs/machcore-group-web-out.log',
    },
  ],
};
