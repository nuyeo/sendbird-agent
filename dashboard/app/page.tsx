"use client";

import { useState, useEffect } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid
} from 'recharts';
import { ThumbsUp, ThumbsDown, Activity, MessageSquare, Clock, TrendingUp, Search, Users } from 'lucide-react';

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
  const [loading, setLoading] = useState(true);
  const [searchTerm, setSearchTerm] = useState("");

  const fetchLogs = async () => {
    try {
      const res = await fetch("http://localhost:8001/api/logs");
      const data = await res.json();
      setLogs(data.logs);
      setLoading(false);
    } catch (error) {
      console.error("Failed to fetch logs:", error);
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 2000);
    return () => clearInterval(interval);
  }, []);

  const sendFeedback = async (id: string, type: "up" | "down") => {
    try {
      await fetch(`http://localhost:8001/api/logs/${id}/feedback`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ feedback: type }),
      });
      setLogs(prev => prev.map(log => log.id === id ? { ...log, feedback: type } : log));
    } catch (e) {
      console.error(e);
    }
  };

  // 통계 계산
  const avgLatency = logs.length > 0
    ? Math.round(logs.reduce((acc, curr) => acc + curr.duration, 0) / logs.length)
    : 0;

  const feedbackStats = logs.reduce((acc, log) => {
    if (log.feedback === 'up') acc.positive++;
    if (log.feedback === 'down') acc.negative++;
    return acc;
  }, { positive: 0, negative: 0 });

  const positiveRate = logs.length > 0
    ? Math.round((feedbackStats.positive / logs.length) * 100)
    : 0;

  const uniqueUsers = new Set(logs.map(log => log.user_id)).size;

  // 검색 필터링
  const filteredLogs = logs.filter(log =>
    log.question.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.answer.toLowerCase().includes(searchTerm.toLowerCase()) ||
    log.user_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  // 그래프 데이터 (최신 20개 역순)
  const chartData = [...logs].reverse().slice(-20).map(log => ({
    time: log.timestamp.split(' ')[1],
    latency: log.duration
  }));

  if (loading) {
    return (
      <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 border-4 border-indigo-200 border-t-indigo-600 rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-gray-600 font-medium">Loading dashboard...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 p-4 md:p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <header className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100 backdrop-blur-sm">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-indigo-600 to-purple-600 bg-clip-text text-transparent">
                Sendbird Agent Monitor
              </h1>
              <p className="text-gray-500 text-sm mt-1">Real-time AI agent performance tracking</p>
            </div>
            <div className="flex items-center gap-3 text-green-600 bg-green-50 px-4 py-2 rounded-full text-sm font-medium shadow-sm">
              <span className="w-2 h-2 bg-green-500 rounded-full animate-pulse"/>
              <span>System Operational</span>
            </div>
          </div>
        </header>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm font-medium">Total Interactions</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">{logs.length}</p>
              </div>
              <div className="p-3 bg-indigo-50 rounded-lg">
                <MessageSquare className="text-indigo-600" size={24} />
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm font-medium">Avg Response Time</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">{avgLatency}ms</p>
              </div>
              <div className="p-3 bg-purple-50 rounded-lg">
                <Clock className="text-purple-600" size={24} />
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm font-medium">Positive Rate</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">{positiveRate}%</p>
              </div>
              <div className="p-3 bg-green-50 rounded-lg">
                <TrendingUp className="text-green-600" size={24} />
              </div>
            </div>
          </div>

          <div className="bg-white p-6 rounded-xl shadow-md border border-gray-100 hover:shadow-lg transition-shadow">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-500 text-sm font-medium">Unique Users</p>
                <p className="text-3xl font-bold text-gray-900 mt-2">{uniqueUsers}</p>
              </div>
              <div className="p-3 bg-amber-50 rounded-lg">
                <Users className="text-amber-600" size={24} />
              </div>
            </div>
          </div>
        </div>

        {/* Chart Section */}
        <div className="bg-white p-6 rounded-2xl shadow-lg border border-gray-100">
          <div className="flex items-center gap-2 mb-6">
            <Activity className="text-indigo-600" size={20}/>
            <h3 className="text-lg font-semibold text-gray-900">Response Latency Trend</h3>
          </div>
          <div className="h-[280px] w-full">
            {chartData.length === 0 ? (
              <div className="h-full flex items-center justify-center text-gray-400">
                <p>No data to display yet</p>
              </div>
            ) : (
              <ResponsiveContainer>
                <LineChart data={chartData}>
                  <defs>
                    <linearGradient id="colorLatency" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="#6366f1" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="#6366f1" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke="#f0f0f0" />
                  <XAxis dataKey="time" tick={{fontSize: 12, fill: '#666'}} />
                  <YAxis tick={{fontSize: 12, fill: '#666'}} />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: 'white',
                      border: '1px solid #e5e7eb',
                      borderRadius: '8px',
                      boxShadow: '0 4px 6px -1px rgba(0, 0, 0, 0.1)'
                    }}
                  />
                  <Line
                    type="monotone"
                    dataKey="latency"
                    stroke="#6366f1"
                    strokeWidth={3}
                    dot={false}
                    fill="url(#colorLatency)"
                  />
                </LineChart>
              </ResponsiveContainer>
            )}
          </div>
        </div>

        {/* Conversation Logs */}
        <div className="bg-white rounded-2xl shadow-lg border border-gray-100 overflow-hidden">
          <div className="p-6 border-b border-gray-100">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <h3 className="text-lg font-semibold text-gray-900">Conversation Logs</h3>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400" size={18} />
                <input
                  type="text"
                  placeholder="Search messages, users..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="pl-10 pr-4 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent w-full sm:w-64"
                />
              </div>
            </div>
          </div>

          {filteredLogs.length === 0 ? (
            <div className="p-12 text-center">
              <MessageSquare className="mx-auto text-gray-300 mb-4" size={48} />
              <p className="text-gray-500 font-medium">No conversations yet</p>
              <p className="text-gray-400 text-sm mt-1">Start chatting with the AI agent to see logs here</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-sm">
                <thead className="bg-gray-50 text-gray-600 uppercase text-xs font-semibold">
                  <tr>
                    <th className="px-6 py-4">Time</th>
                    <th className="px-6 py-4">User</th>
                    <th className="px-6 py-4">Conversation</th>
                    <th className="px-6 py-4 text-center">Latency</th>
                    <th className="px-6 py-4 text-center">Feedback</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {filteredLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-6 py-4 text-gray-500 whitespace-nowrap text-xs">
                        {log.timestamp}
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex items-center gap-2">
                          <div className="w-8 h-8 bg-gradient-to-br from-indigo-400 to-purple-400 rounded-full flex items-center justify-center text-white text-xs font-bold">
                            {log.user_id.charAt(0).toUpperCase()}
                          </div>
                          <span className="text-gray-700 font-medium text-sm">{log.user_id}</span>
                        </div>
                      </td>
                      <td className="px-6 py-4 max-w-lg">
                        <div className="space-y-2">
                          <div className="flex gap-2">
                            <span className="font-bold text-gray-700 text-xs">Q:</span>
                            <p className="text-gray-800">{log.question}</p>
                          </div>
                          <div className="flex gap-2">
                            <span className="font-bold text-indigo-600 text-xs">A:</span>
                            <p className="text-gray-600">{log.answer}</p>
                          </div>
                        </div>
                      </td>
                      <td className="px-6 py-4 text-center">
                        <span className={`inline-block px-3 py-1 rounded-full text-xs font-medium ${
                          log.duration < 1000
                            ? 'bg-green-100 text-green-700'
                            : log.duration < 2000
                            ? 'bg-yellow-100 text-yellow-700'
                            : 'bg-red-100 text-red-700'
                        }`}>
                          {log.duration}ms
                        </span>
                      </td>
                      <td className="px-6 py-4">
                        <div className="flex gap-2 justify-center">
                          <button
                            onClick={() => sendFeedback(log.id, "up")}
                            className={`p-2 rounded-lg transition-all ${
                              log.feedback === 'up'
                                ? 'bg-green-100 text-green-600 shadow-sm'
                                : 'hover:bg-gray-100 text-gray-400 hover:text-green-600'
                            }`}
                          >
                            <ThumbsUp size={16} />
                          </button>
                          <button
                            onClick={() => sendFeedback(log.id, "down")}
                            className={`p-2 rounded-lg transition-all ${
                              log.feedback === 'down'
                                ? 'bg-red-100 text-red-600 shadow-sm'
                                : 'hover:bg-gray-100 text-gray-400 hover:text-red-600'
                            }`}
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
          )}
        </div>
      </div>
    </main>
  );
}