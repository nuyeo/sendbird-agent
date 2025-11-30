"use client";

import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { ThumbsUp, ThumbsDown, Activity, MessageSquare } from 'lucide-react';

interface Log {
  id: string;
  timestamp: string;
  user_id: string;
  question: string;
  answer: string;
  duration: number;
  feedback: "up" | "down" | null;
}

export default function Home() {
  const [logs, setLogs] = useState<Log[]>([]);

  const fetchLogs = async () => {
    try {
      const res = await fetch("http://localhost:8001/api/logs");
      const data = await res.json();
      setLogs(data.logs);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  // 피드백 전송 함수
  const sendFeedback = async (id: string, type: "up" | "down") => {
    try {
      await fetch(`http://localhost:8001/api/logs/${id}/feedback`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: type }),
      });
      // 낙관적 업데이트 (화면에서 바로 반영)
      setLogs(prev => prev.map(log => log.id === id ? { ...log, feedback: type } : log));
    } catch (e) {
      console.error(e);
    }
  };

  // 그래프 데이터 (최신 20개 역순)
  const chartData = [...logs].reverse().slice(-20).map(log => ({
    time: log.timestamp.split(' ')[1],
    latency: log.duration
  }));

  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <header className="flex justify-between items-center bg-white p-6 rounded-2xl shadow-sm">
          <h1 className="text-2xl font-bold text-gray-900">🤖 Sendbird Agent Monitor</h1>
          <div className="flex items-center gap-2 text-green-600 bg-green-50 px-3 py-1 rounded-full text-sm font-medium">
            <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"/> Operational
          </div>
        </header>

        {/* 그래프 영역 */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          <div className="lg:col-span-2 bg-white p-6 rounded-2xl shadow-sm">
            <h3 className="text-gray-500 text-sm mb-4 flex items-center gap-2">
              <Activity size={16}/> Response Latency (ms)
            </h3>
            <div className="h-[200px] w-full">
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="time" tick={{fontSize: 12}} />
                  <YAxis tick={{fontSize: 12}} />
                  <Tooltip />
                  <Line type="monotone" dataKey="latency" stroke="#6366f1" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="bg-white p-6 rounded-2xl shadow-sm flex flex-col justify-center items-center">
             <div className="text-center">
                <p className="text-gray-500 text-sm">Total Interactions</p>
                <p className="text-5xl font-bold text-gray-900 mt-2">{logs.length}</p>
             </div>
          </div>
        </div>

        {/* 로그 테이블 */}
        <div className="bg-white rounded-2xl shadow-sm overflow-hidden">
          <table className="w-full text-left text-sm">
            <thead className="bg-gray-50 text-gray-600 uppercase font-semibold">
              <tr>
                <th className="px-6 py-4">Time</th>
                <th className="px-6 py-4">Message</th>
                <th className="px-6 py-4">Latency</th>
                <th className="px-6 py-4">Feedback</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {logs.map((log) => (
                <tr key={log.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 text-gray-500 whitespace-nowrap">{log.timestamp}</td>
                  <td className="px-6 py-4">
                    <div className="space-y-1">
                      <div className="flex gap-2"><span className="font-bold text-gray-700">Q:</span> {log.question}</div>
                      <div className="flex gap-2 text-gray-600"><span className="font-bold text-blue-600">A:</span> {log.answer}</div>
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    <span className={`px-2 py-1 rounded text-xs ${log.duration < 1000 ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'}`}>
                      {log.duration}ms
                    </span>
                  </td>
                  <td className="px-6 py-4">
                    <div className="flex gap-2">
                      <button
                        onClick={() => sendFeedback(log.id, "up")}
                        className={`p-1.5 rounded transition-colors ${log.feedback === 'up' ? 'bg-green-100 text-green-600' : 'hover:bg-gray-100 text-gray-400'}`}
                      >
                        <ThumbsUp size={16} />
                      </button>
                      <button
                        onClick={() => sendFeedback(log.id, "down")}
                        className={`p-1.5 rounded transition-colors ${log.feedback === 'down' ? 'bg-red-100 text-red-600' : 'hover:bg-gray-100 text-gray-400'}`}
                      >
                        <ThumbsDown size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </main>
  );
}