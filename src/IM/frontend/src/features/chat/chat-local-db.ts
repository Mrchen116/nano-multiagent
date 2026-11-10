/** Open the origin-scoped chat database without replacing in-flight legacy send attempts.
 *
 * Returns:
 *   A caller-owned connection. Account IDs remain part of every store key; IndexedDB's
 *   origin boundary supplies service isolation. Upgrade adds only private leave watermarks.
 */
export function openChatDatabase(): Promise<IDBDatabase> {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open('im-message-attempts', 2);
    request.onupgradeneeded = () => {
      const db = request.result;
      if (!db.objectStoreNames.contains('attempts')) {
        const attempts = db.createObjectStore('attempts', {keyPath: ['userId', 'conversationId', 'key']});
        attempts.createIndex('conversation', ['userId', 'conversationId']);
        attempts.createIndex('user', 'userId');
      }
      if (!db.objectStoreNames.contains('watermarks')) {
        const watermarks = db.createObjectStore('watermarks', {keyPath: ['userId', 'conversationId']});
        watermarks.createIndex('user', 'userId');
      }
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}
