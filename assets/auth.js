import { firebaseConfig, firebaseEnabled } from "./firebase-config.js";

const LOCAL_KEY = "market-radar-user-data-v9";
const AUTH_EVENT = "market-auth-changed";
const DATA_EVENT = "market-user-data-changed";

const defaultData = {
  watchSymbols: [],
  favoriteEventIds: [],
  reminders: {},
  preferences: {},
  updatedAt: null
};

let currentUser = null;
let auth = null;
let db = null;
let firebaseApi = null;

function readLocal() {
  try {
    return { ...defaultData, ...JSON.parse(localStorage.getItem(LOCAL_KEY) || "{}") };
  } catch {
    return { ...defaultData };
  }
}

function writeLocal(data) {
  const payload = { ...defaultData, ...data, updatedAt: new Date().toISOString() };
  localStorage.setItem(LOCAL_KEY, JSON.stringify(payload));
  window.dispatchEvent(new CustomEvent(DATA_EVENT, { detail: payload }));
  return payload;
}

async function initFirebase() {
  if (!firebaseEnabled) {
    notifyAuth();
    return;
  }
  try {
    const appMod = await import("https://www.gstatic.com/firebasejs/12.1.0/firebase-app.js");
    const authMod = await import("https://www.gstatic.com/firebasejs/12.1.0/firebase-auth.js");
    const dbMod = await import("https://www.gstatic.com/firebasejs/12.1.0/firebase-firestore.js");
    const app = appMod.initializeApp(firebaseConfig);
    auth = authMod.getAuth(app);
    db = dbMod.initializeFirestore(app, {
      localCache: dbMod.persistentLocalCache({ tabManager: dbMod.persistentMultipleTabManager() })
    });
    firebaseApi = { ...authMod, ...dbMod };
    await authMod.getRedirectResult(auth).catch(() => null);
    authMod.onAuthStateChanged(auth, async (user) => {
      currentUser = user || null;
      if (currentUser) await pullCloudData();
      notifyAuth();
    });
  } catch (error) {
    console.error("Firebase initialization failed", error);
    notifyAuth(String(error?.message || error));
  }
}

function notifyAuth(error = "") {
  window.dispatchEvent(new CustomEvent(AUTH_EVENT, {
    detail: {
      enabled: firebaseEnabled,
      user: currentUser ? {
        uid: currentUser.uid,
        displayName: currentUser.displayName || "Google 使用者",
        email: currentUser.email || "",
        photoURL: currentUser.photoURL || ""
      } : null,
      error
    }
  }));
}

async function pullCloudData() {
  if (!currentUser || !db || !firebaseApi) return readLocal();
  const ref = firebaseApi.doc(db, "users", currentUser.uid, "private", "settings");
  const snap = await firebaseApi.getDoc(ref);
  const local = readLocal();
  if (snap.exists()) {
    const cloud = { ...defaultData, ...snap.data() };
    const chosen = String(cloud.updatedAt || "") >= String(local.updatedAt || "") ? cloud : local;
    writeLocal(chosen);
    if (chosen === local) await pushCloudData(local);
    return chosen;
  }
  await pushCloudData(local);
  return local;
}

async function pushCloudData(data) {
  if (!currentUser || !db || !firebaseApi) return;
  const ref = firebaseApi.doc(db, "users", currentUser.uid, "private", "settings");
  await firebaseApi.setDoc(ref, { ...data, updatedAt: new Date().toISOString() }, { merge: true });
}

async function saveUserData(patch) {
  const next = writeLocal({ ...readLocal(), ...patch });
  if (currentUser) {
    try { await pushCloudData(next); }
    catch (error) { console.warn("Cloud sync failed", error); }
  }
  return next;
}

async function signInGoogle() {
  if (!firebaseEnabled || !auth || !firebaseApi) {
    throw new Error("尚未設定 Firebase，請先填入 assets/firebase-config.js。");
  }
  const provider = new firebaseApi.GoogleAuthProvider();
  provider.setCustomParameters({ prompt: "select_account" });
  const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent);
  if (isMobile) return firebaseApi.signInWithRedirect(auth, provider);
  return firebaseApi.signInWithPopup(auth, provider);
}

async function signOutUser() {
  if (auth && firebaseApi) await firebaseApi.signOut(auth);
  currentUser = null;
  notifyAuth();
}

window.MarketAuth = {
  firebaseEnabled,
  getUser: () => currentUser,
  getData: readLocal,
  saveData: saveUserData,
  signInGoogle,
  signOut: signOutUser,
  useGuest: () => notifyAuth(),
  events: { AUTH_EVENT, DATA_EVENT }
};

initFirebase();
setTimeout(() => notifyAuth(), 0);
