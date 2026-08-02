// 從 Firebase Console → Project settings → Your apps → Web app 複製設定後貼到這裡。
// apiKey 不是秘密；真正的資料保護要靠 Firestore Security Rules。
export const firebaseConfig = {
  apiKey: "",
  authDomain: "",
  projectId: "",
  storageBucket: "",
  messagingSenderId: "",
  appId: ""
};

export const firebaseEnabled = Boolean(
  firebaseConfig.apiKey &&
  firebaseConfig.authDomain &&
  firebaseConfig.projectId &&
  firebaseConfig.appId
);
