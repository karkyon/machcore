"use client";
import { useEffect, useState } from "react";

export default function TestPage() {
  const [machines, setMachines] = useState<any[]>([]);
  const [users, setUsers]       = useState<any[]>([]);
  const [error, setError]       = useState<string | null>(null);

  useEffect(() => {
    Promise.all([
      fetch("/api/machines").then(r => r.json()),
      fetch("/api/users").then(r => r.json()),
    ])
      .then(([m, u]) => { setMachines(m); setUsers(u); })
      .catch(e => setError(String(e)));
  }, []);

  return (
    <div className="p-8 font-mono">
      <h1 className="text-2xl font-bold mb-6">
        MachCore API 疎通確認
      </h1>

      {error && (
        <div className="bg-red-100 text-red-800 p-4 rounded mb-6">
          エラー: {error}
        </div>
      )}

      <section className="mb-8">
        <h2 className="text-lg font-bold mb-2">
          GET /api/machines ({machines.length}件)
        </h2>
        <pre className="bg-gray-100 p-4 rounded text-sm overflow-auto">
          {JSON.stringify(machines, null, 2)}
        </pre>
      </section>

      <section>
        <h2 className="text-lg font-bold mb-2">
          GET /api/users ({users.length}件)
        </h2>
        <pre className="bg-gray-100 p-4 rounded text-sm overflow-auto">
          {JSON.stringify(users, null, 2)}
        </pre>
      </section>
    </div>
  );
}
