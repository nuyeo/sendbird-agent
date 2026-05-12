// k6 WebSocket 부하 테스트 (베이스라인용)
//
// 시나리오: ramping-vus, 30초 ramp-up → 50 VU로 3분 유지 → 30초 ramp-down.
// 각 VU는 사전 발급된 토큰으로 /ws/{user_id}에 접속, user_message 1회 송신,
// ai_response 수신까지의 지연을 ai_message_latency_ms로 기록한다.
//
// 실행 전 준비:
//   python tests/load/seed_tokens.py --count 100
//
// 실행:
//   k6 run tests/load/baseline.js
//   (대상 서버 변경: k6 run -e BASE_WS=ws://staging.example.com tests/load/baseline.js)

import ws from 'k6/ws';
import { check, sleep } from 'k6';
import { SharedArray } from 'k6/data';
import { Trend, Counter, Rate } from 'k6/metrics';

const tokens = new SharedArray('tokens', function () {
  return JSON.parse(open('./tokens.json'));
});

// FAQ 조회와 tool calling을 골고루 자극하는 샘플 쿼리.
const QUERIES = [
  '환불 정책이 어떻게 되나요?',
  '배송비가 얼마인가요?',
  '오늘 주문하면 언제 발송되나요?',
  '환불 처리는 얼마나 걸리나요?',
  '개봉한 제품도 환불 가능한가요?',
  '주문번호 A101 상태 알려줘',
  '주문 B202 취소해주세요',
  '주문 C303 환불 얼마 가능한가요?',
  '상담원 연결해주세요',
];

const BASE_WS = __ENV.BASE_WS || 'ws://localhost:8001';
const RESPONSE_TIMEOUT_MS = parseInt(__ENV.RESPONSE_TIMEOUT_MS || '30000');

// 사용자 지정 메트릭
const messageLatency = new Trend('ai_message_latency_ms', true);
const messageSuccess = new Rate('ai_message_success');
const messageErrors = new Counter('ai_message_errors');
const wsHandshakeOk = new Rate('ws_handshake_ok');

export const options = {
  scenarios: {
    baseline: {
      executor: 'ramping-vus',
      startVUs: 0,
      stages: [
        { duration: '30s', target: 50 },
        { duration: '3m', target: 50 },
        { duration: '30s', target: 0 },
      ],
      gracefulRampDown: '30s',
    },
  },
  // 실패해도 측정은 끝까지 진행해서 베이스라인 수치를 확보해야 하므로
  // abortOnFail 미사용. 임계치는 보수적으로 설정해 회귀 감지용으로만 사용.
  thresholds: {
    ai_message_success: ['rate>0.90'],
    ai_message_latency_ms: ['p(95)<15000'],
    ws_handshake_ok: ['rate>0.99'],
  },
};

function pickQuery() {
  return QUERIES[Math.floor(Math.random() * QUERIES.length)];
}

export default function () {
  const slot = tokens[(__VU - 1) % tokens.length];
  const url = `${BASE_WS}/ws/${slot.user_id}?token=${encodeURIComponent(slot.token)}`;
  const query = pickQuery();

  const res = ws.connect(url, {}, function (socket) {
    let sentAt = 0;
    let responded = false;

    socket.on('open', () => {
      sentAt = Date.now();
      socket.send(
        JSON.stringify({
          type: 'user_message',
          message: query,
        })
      );
    });

    socket.on('message', (raw) => {
      let data;
      try {
        data = JSON.parse(raw);
      } catch (e) {
        return;
      }
      if (data.type === 'ai_response') {
        messageLatency.add(Date.now() - sentAt);
        messageSuccess.add(true);
        responded = true;
        socket.close();
      } else if (data.type === 'error') {
        messageErrors.add(1);
        messageSuccess.add(false);
        responded = true;
        socket.close();
      }
      // type === 'typing' 등 진행 알림은 무시
    });

    socket.on('error', () => {
      if (!responded) {
        messageErrors.add(1);
        messageSuccess.add(false);
      }
    });

    socket.setTimeout(() => {
      if (!responded) {
        messageErrors.add(1);
        messageSuccess.add(false);
        socket.close();
      }
    }, RESPONSE_TIMEOUT_MS);
  });

  const handshakeOk = res && res.status === 101;
  wsHandshakeOk.add(handshakeOk ? 1 : 0);
  check(res, { 'WS handshake 101': () => handshakeOk });

  // 실유저 페이싱 흉내: 메시지 간 짧은 휴식
  sleep(1);
}
