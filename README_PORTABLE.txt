PandaDesktopPet · Apink 熊貓桌面寵物

非官方、非營利粉絲創作（Windows 桌面小寵物） / 비공식·비영리 팬 창작물 (Windows 데스크톱 펫) / Unofficial, non-commercial fan project (Windows desktop pet).

繁中聲明：本專案是非官方、非營利粉絲創作，與 Apink 或其經紀公司無合作關係，未取得權利人授權。不販售、不投放廣告、不接受贊助，亦無付費功能。權利人可透過本專案 GitHub Issues 聯繫（詳見同資料夾之 ASSETS-LICENSE.md），收到通知後將立即停止相關素材散布並下架。非營利不代表取得授權。

한국어 안내: 본 프로젝트는 영리 목적이 없는 비공식 팬 창작물입니다. Apink 및 소속사와 제휴 관계가 없으며, 공식 승인이나 이용 허락을 받지 않았습니다. 판매·광고·후원·유료 기능을 운영하지 않습니다. 권리자는 이 저장소의 GitHub Issues로 문의해 주시면(같은 폴더의 ASSETS-LICENSE.md 참고) 관련 소재의 배포를 즉시 중단하고 삭제하겠습니다. 비영리 목적이라는 사실이 이용 허락을 의미하지는 않습니다.

English notice: This unofficial, non-commercial fan project has no sales, advertising, donations, or paid features. It is not affiliated with or endorsed by Apink or their management agencies; no authorization has been obtained from the rights holders. Rights holders may contact us via this repository's GitHub Issues (see ASSETS-LICENSE.md in this folder), and distribution of the relevant assets will stop immediately with prompt removal. Non-commercial use does not imply permission.

============================================================
繁體中文
============================================================

【系統需求與下載快速上手】
- 支援環境：僅支援 Windows 10 / 11（64-bit），不支援 macOS、Linux 或手機裝置。
- 已測試環境：Windows 10 / 11（64-bit）、96–192 DPI（100%–200% 縮放）、單螢幕與雙螢幕。
1. 請只從本專案官方 GitHub Releases 下載，切勿下載不明轉載（實際檔案以該次 Release 頁面附件為準）。
2. 免安裝版 PandaDesktopPet-portable.zip（不需要安裝 Python）：核對 SHA-256 後完整解壓縮，執行 PandaDesktopPet/PandaDesktopPet.exe，請保留旁邊的 _internal 資料夾，不要直接在 ZIP 裡執行。
3. 安裝版 PandaDesktopPet-Setup.exe（不需要安裝 Python）：核對 SHA-256 後執行安裝（預設安裝至 %LOCALAPPDATA%\Programs\PandaDesktopPet，免管理員權限）。
4. 首次啟動可輸入暱稱；生日可略過，之後可在設定隨時修改。

不用輸入路徑的 SHA-256 核對法：
開啟 PowerShell，輸入 Get-FileHash （後面空一格），把下載的 .zip 或 .exe 拖進視窗，再按 Enter，核對完整英數字是否與同一個官方 Release 的 SHA256SUMS.txt 完全相同；不一致請勿執行。
  Get-FileHash "下載檔案的完整路徑.zip" -Algorithm SHA256
  certutil -hashfile "下載檔案的完整路徑.zip" SHA256

SmartScreen 與防毒誤報提醒：
- 若 Windows SmartScreen 警告未識別程式，請先核對官方來源與 SHA-256，確認無誤後再從「其他資訊」決定是否執行；勿停用整體防護。
- 若確認來源與 SHA-256 無誤，但解壓縮後發現 PandaDesktopPet.exe 消失，請至「Windows 安全性 -> 病毒與威脅防護 -> 保護歷程記錄」查看是否遭防毒軟體誤判隔離。

【功能特色】
- 五位熊貓：初瓏（隆咚 / Rongdoong）、普美（普咚 / Bbomdoong）、恩地（恩咚 / Meungdoong）、南珠（南咚 / Namdoong）、夏榮（夏咚 / Hadoong）；自動輪值或手動選角，小 / 中 / 大尺寸與高 DPI 縮放。
- 走路、睡覺、餵食、氣泡互動、角色檔案卡、生日提醒、節慶換裝、跨年倒數與五人集體慶祝；共 56 種食物。
- 14 個待機畫面 = 4 個手繪動態場景 + 10 張插畫桌布（占卜室已包含在這 10 張內；另有獨立恩地占卜對話框，不另算一張待機桌布）。
- 大巨蛋棒球應援、普美正面歡呼、恩地個唱想像舞台 8 套服裝（含開場服裝）；粉絲想像場景不代表真實演出公告，占卜僅供娛樂。
- 4 款自訂游標 + 1 個系統預設選項，可僅程式內或全域套用，正常退出時自動還原全域游標。繁中 / 韓文 / 英文即時切換。

【操作、設定與移除】
- 拖曳移動，右鍵開啟選單。預設全域待機快捷鍵 Ctrl+Shift+S 可調整；F9 只在桌寵視窗取得焦點時切換待機。
- 待機左右鍵換景；H 隱藏或顯示時鐘與提示，熊貓仍保留。其他按鍵或滑鼠操作離開待機。
- 透過系統匣（工作列右下角圖示）右鍵選單可顯示／隱藏或結束程式。
- 全域游標異常復原：若程式崩潰、強制結束或系統異常關機導致全域游標未還原，請至 Windows「滑鼠內容 -> 指標 -> 使用預設值 -> 套用」一鍵還原，或重開桌寵後將游標切回系統預設。
- 解除安裝：安裝版可從 Windows「設定 -> 應用程式」解除安裝；免安裝版請先停用開機自啟、退出，再刪除程式資料夾。另刪 %APPDATA%\PandaDesktopPet 才會清除暱稱、生日、設定與紀錄。

【隱私與系統存取說明】
- 本機儲存：暱稱、生日、設定與餵食紀錄僅保存在本機 %APPDATA%\PandaDesktopPet。
- 通知轉報：預設開啟（可於設定隨時關閉或開啟隱私模式），以 SQLite 唯讀模式讀取本機 Windows 通知資料庫以氣泡提醒新通知，不修改或刪除系統通知，最近 20 則僅暫存於記憶體（RAM），關閉程式即清除。
- 網路連線：100% 本機離線執行，無任何網路連線呼叫、無遙測或自動上傳。
- 資料刪除：刪除 %APPDATA%\PandaDesktopPet 即可徹底清除。

【常見問題（FAQ）】
1. 解壓縮後找不到主程式或無法啟動：請確認完整解壓縮並保留 _internal；若 .exe 消失請檢查 Windows 安全性保護歷程記錄。
2. 畫面上找不到熊貓：請右鍵點選工作列右下角系統匣圖示顯示或重置位置。
3. 跳出 SmartScreen 警告：核對官方來源與 SHA-256 無誤後，點選「其他資訊 -> 仍要執行」。
4. 強制結束後游標未還原：至 Windows「滑鼠內容 -> 指標 -> 使用預設值 -> 套用」即可恢復。

【素材與授權】
程式碼使用 MIT（詳見同資料夾 LICENSE）；角色、桌布、游標、台詞與介紹圖另受同資料夾 ASSETS-LICENSE.md 約束。assets.pak 是索引封裝，不是加密或 DRM，請勿抽出素材另用。

============================================================
한국어
============================================================

[시스템 요구 사항 및 다운로드 빠른 시작]
- 지원 환경: Windows 10 / 11 (64-bit) 전용 (macOS, Linux, 모바일 미지원).
- 테스트 환경: Windows 10 / 11 (64-bit), 96-192 DPI (100%-200%), 단일 및 듀얼 모니터.
1. 이 프로젝트의 공식 GitHub Releases에서만 다운로드하세요 (실제 파일은 해당 Release 첨부 파일 기준).
2. 포터블 ZIP (PandaDesktopPet-portable.zip, Python 불필요): SHA-256 확인 후 전체 압축을 풀고 PandaDesktopPet/PandaDesktopPet.exe를 실행하세요 (_internal 폴더 함께 보관).
3. 설치 프로그램 (PandaDesktopPet-Setup.exe, Python 불필요): SHA-256 확인 후 실행해 설치하세요 (기본 경로 %LOCALAPPDATA%\Programs\PandaDesktopPet, 관리자 권한 불필요).
4. 처음 실행 시 닉네임을 입력할 수 있으며, 생일은 생략하거나 나중에 설정에서 변경할 수 있습니다.

SHA-256 확인:
  Get-FileHash "다운로드한 파일의 전체 경로.zip" -Algorithm SHA256
  certutil -hashfile "다운로드한 파일의 전체 경로.zip" SHA256

SmartScreen 및 백신 오탐 안내:
- SmartScreen 경고 시 공식 출처와 SHA-256을 먼저 확인한 뒤 '추가 정보'에서 실행 여부를 결정하세요.
- 압축 해제 후 .exe가 보이지 않는다면 'Windows 보안 -> 바이러스 및 위협 방지 -> 보호 기록'을 확인하세요.

[기능]
- 초롱 (롱둥이 / Rongdoong), 보미 (뽐둥이 / Bbomdoong), 은지 (믕둥이 / Meungdoong), 남주 (남둥이 / Namdoong), 하영 (하둥이 / Hadoong). 자동 순환 또는 수동 선택, 작게 / 보통 / 크게 크기와 고 DPI 배율 지원.
- 걷기, 잠자기, 먹이 주기, 말풍선, 프로필 카드, 생일 알림, 명절 의상, 새해 카운트다운과 단체 축하; 음식 56종.
- 대기 화면 14개 = 직접 그린 장면 4개 + 일러스트 배경 10개 (점술방 포함).
- 돔 야구 응원, 보미 정면 응원, 은지 상상 솔로 콘서트 의상 8벌 (오프닝 포함).
- 사용자 지정 커서 4종 + 시스템 기본값 1개, 정상 종료 시 전역 커서 자동 복원. 번체 중국어 / 한국어 / 영어 즉시 전환.

[조작, 설정, 개인정보 및 삭제]
- 드래그 이동, 오른쪽 클릭 메뉴, 전역 대기 단축키 Ctrl+Shift+S, 포커스 시 F9, 대기 중 좌우 방향키 장면 전환, H 시계 숨김/표시.
- 작업 표시줄 오른쪽 아래 시스템 트레이 아이콘에서 종료할 수 있습니다.
- 강제 종료 등으로 전역 커서가 복구되지 않았다면 Windows '마우스 속성 -> 포인터 -> 기본값 사용 -> 적용'을 누르거나 앱을 다시 열어 시스템 기본값으로 변경하세요.
- 로컬 저장: %APPDATA%\PandaDesktopPet. 100% 오프라인 로컬 실행이며 원격 측정이나 자동 업로드가 없습니다. 알림 전달 기능은 기본값으로 켜져 있으며(설정에서 해제 및 보호 모드 가능), 읽기 전용으로 최근 20건만 RAM에 임시 보관합니다.
- 삭제: 설치 버전은 Windows '설정 -> 앱'에서 제거, 포터블 버전은 자동 시작 해제 후 폴더 삭제. 사용자 데이터까지 삭제하려면 %APPDATA%\PandaDesktopPet 폴더를 삭제하세요.

[소재와 라이선스]
코드는 MIT (LICENSE), 미술·텍스트 소재는 ASSETS-LICENSE.md를 따릅니다. assets.pak은 인덱스 묶음이며 암호화나 DRM이 아닙니다.

============================================================
English
============================================================

[System requirements & quick start]
- Supported OS: Windows 10 / 11 (64-bit) only (macOS, Linux, and mobile not supported).
- Tested: Windows 10 / 11 (64-bit), 96-192 DPI (100%-200%), single and dual monitors.
1. Download only from this project's official GitHub Releases (available files follow the attachments on that Release page).
2. Portable ZIP (PandaDesktopPet-portable.zip, no Python required): verify SHA-256, extract the entire archive, and run PandaDesktopPet/PandaDesktopPet.exe (keep _internal beside it; do not run inside the ZIP).
3. Installer (PandaDesktopPet-Setup.exe, no Python required): verify SHA-256 and run setup (installs per-user to %LOCALAPPDATA%\Programs\PandaDesktopPet without admin rights).
4. Nickname can be entered on first launch; birthday is optional and editable in Settings.

SHA-256 verification:
  Get-FileHash "full path to your downloaded file.zip" -Algorithm SHA256
  certutil -hashfile "full path to your downloaded file.zip" SHA256

SmartScreen & antivirus false-positive notice:
- If SmartScreen warns about an unrecognized app, verify the official source and SHA-256 first before choosing More info -> Run anyway.
- If PandaDesktopPet.exe disappears after extraction, check Windows Security -> Virus & threat protection -> Protection history.

[Features]
- Five pandas: Chorong (Rongdoong), Bomi (Bbomdoong), Eunji (Meungdoong), Namjoo (Namdoong), and Hayoung (Hadoong); automatic rotation or manual selection, Small / Medium / Large sizes, and high-DPI scaling.
- Walking, sleeping, feeding, speech bubbles, profile cards, birthday reminders, seasonal outfits, New Year countdowns, and group celebrations; 56 foods.
- 14 standby views = 4 drawn scenes + 10 illustrated wallpapers (fortune room included).
- Dome baseball cheering, Bomi's front-facing cheer, and 8 outfits (including the opening outfit) for Eunji's imagined solo concert.
- 4 custom cursors + 1 system-default option, app-only or global, with automatic restoration on normal exit. Live Traditional Chinese / Korean / English switching.

[Controls, privacy, and removal]
- Drag to move; right-click for menu. Global standby shortcut: Ctrl+Shift+S; F9 when focused. In standby: Left / Right switches scenes, H toggles clock/hints.
- Exit from the system tray icon context menu (bottom-right of the taskbar).
- Stuck global cursor recovery: after a crash or forced kill, open Windows Mouse Properties -> Pointers -> Use Default -> Apply, or relaunch the app and select System Default cursor.
- Privacy & network: 100% offline local execution with no telemetry or uploads. User data lives in %APPDATA%\PandaDesktopPet. The notification bubble relay is enabled by default (can be disabled anytime in Settings, with Privacy Mode), opens Windows' toast DB strictly read-only, and keeps only the latest 20 items in RAM.
- Removal: uninstall the Setup version via Windows Settings -> Apps; for portable, disable autostart, exit, and delete the folder. Delete %APPDATA%\PandaDesktopPet to remove all user data.

[Assets and licensing]
Code is MIT licensed (see LICENSE). Artwork and text follow ASSETS-LICENSE.md. assets.pak is an indexed container, not encryption or DRM. Do not extract assets for other uses.
