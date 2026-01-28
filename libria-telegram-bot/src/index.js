export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    
    // Endpoint 1: Webhook de Telegram
    if (url.pathname === '/webhook' && request.method === 'POST') {
      return handleTelegramWebhook(request, env);
    }
    
    // Endpoint 2: Consultar chat_id (para n8n)
    if (url.pathname === '/get-chat-id' && request.method === 'GET') {
      return handleGetChatId(request, env);
    }
    
    return new Response('LibrIA Telegram Bot - OK', { status: 200 });
  }
};

// ============================================================
// WEBHOOK TELEGRAM
// ============================================================
async function handleTelegramWebhook(request, env) {
  try {
    const update = await request.json();
    
    // Verificar que es un mensaje con /start
    if (!update.message?.text?.startsWith('/start')) {
      return new Response('OK', { status: 200 });
    }
    
    const message = update.message;
    const chatId = message.chat.id;
    const text = message.text;
    
    // Extraer código: /start ABC123
    const parts = text.split(' ');
    if (parts.length < 2) {
      await sendTelegramMessage(env, chatId, 
        "❌ Uso incorrecto.\n\n" +
        "Debes usar: /start CODIGO\n" +
        "El código lo obtienes en la app LibrIA."
      );
      return new Response('OK', { status: 200 });
    }
    
    const codigo = parts[1].toUpperCase();
    
    // Calcular firma HMAC
    const firma = await calcularFirma(codigo, env.TELEGRAM_SECRET_KEY);
    
    // Guardar en KV
    await env.LIBRIA_KV.put(`codigo:${codigo}`, JSON.stringify({
      chat_id: chatId,
      firma: firma,
      timestamp: Date.now()
    }), {
      expirationTtl: 600 // Expira en 10 minutos
    });
    
    // Responder al usuario
    await sendTelegramMessage(env, chatId,
      "✅ Bot activado correctamente\n\n" +
      "Tu código de verificación:\n" +
      `\`${firma}\`\n\n` +
      "Copia este código y pégalo en la app LibrIA.\n\n" +
      "⏰ *El código expira en 10 minutos.*",
      true // Markdown
    );
    
    return new Response('OK', { status: 200 });
    
  } catch (error) {
    console.error('Error:', error);
    return new Response('Error', { status: 500 });
  }
}

// ============================================================
// CONSULTAR CHAT_ID (para n8n)
// ============================================================
async function handleGetChatId(request, env) {
  const url = new URL(request.url);
  const codigo = url.searchParams.get('codigo');
  
  if (!codigo) {
    return Response.json({ error: 'Falta parámetro: codigo' }, { status: 400 });
  }
  
  // Buscar en KV
  const data = await env.LIBRIA_KV.get(`codigo:${codigo.toUpperCase()}`);
  
  if (!data) {
    return Response.json({ error: 'Código no encontrado' }, { status: 404 });
  }
  
  const parsed = JSON.parse(data);
  
  return Response.json({
    chat_id: parsed.chat_id,
    timestamp: parsed.timestamp
  });
}

// ============================================================
// HELPERS
// ============================================================
async function calcularFirma(codigo, secret) {
  const encoder = new TextEncoder();
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(secret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  );
  
  const signature = await crypto.subtle.sign(
    'HMAC',
    key,
    encoder.encode(codigo)
  );
  
  const hashArray = Array.from(new Uint8Array(signature));
  const hashHex = hashArray.map(b => b.toString(16).padStart(2, '0')).join('');
  
  return hashHex.substring(0, 8).toUpperCase();
}

async function sendTelegramMessage(env, chatId, text, markdown = false) {
  const url = `https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`;
  
  const body = {
    chat_id: chatId,
    text: text
  };
  
  if (markdown) {
    body.parse_mode = 'Markdown';
  }
  
  await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  });
}