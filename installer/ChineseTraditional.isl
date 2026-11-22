; *** Inno Setup version 6.5.0+ Traditional Chinese (Taiwan) messages ***
; Created for PandaDesktopPet installer (zh_TW / ko / en)

[LangOptions]
LanguageName=繁體中文
LanguageID=$0404
LanguageCodePage=950

[Messages]

; *** Application titles
SetupAppTitle=安裝程式
SetupWindowTitle=安裝 - %1
UninstallAppTitle=解除安裝
UninstallAppFullTitle=解除安裝 %1

; *** Misc. common
InformationTitle=資訊
ConfirmTitle=確認
ErrorTitle=錯誤

; *** SetupLdr messages
SetupLdrStartupMessage=即將安裝 %1。是否要繼續？
LdrCannotCreateTemp=無法建立暫存檔案，安裝已中止
LdrCannotExecTemp=無法在暫存資料夾執行檔案，安裝已中止
HelpTextNote=

; *** Startup error messages
LastErrorMessage=%1.%n%n錯誤 %2: %3
SetupFileMissing=安裝資料夾中找不到檔案 %1。請修正問題或重新取得程式安裝檔。
SetupFileCorrupt=安裝檔案已損毀。請重新取得程式安裝檔。
SetupFileCorruptOrWrongVer=安裝檔案已損毀，或與此版本安裝程式不相容。請修正問題或重新取得程式安裝檔。
InvalidParameter=命令列傳入了無效的參數:%n%n%1
SetupAlreadyRunning=安裝程式已經在執行中。
WindowsVersionNotSupported=此程式不支援您電腦目前執行的 Windows 版本。
WindowsServicePackRequired=此程式需要 %1 Service Pack %2 或更新版本。
NotOnThisPlatform=此程式無法在 %1 上執行。
OnlyOnThisPlatform=此程式必須在 %1 上執行。
OnlyOnTheseArchitectures=此程式僅能安裝於支援下列處理器架構的 Windows 版本:%n%n%1
WinVersionTooLowError=此程式需要 %1 版本 %2 或更新版本。
WinVersionTooHighError=此程式無法安裝於 %1 版本 %2 或更新版本。
AdminPrivilegesRequired=安裝此程式時，您必須以系統管理員身分登入。
PowerUserPrivilegesRequired=安裝此程式時，您必須以系統管理員或 Power Users 群組成員身分登入。
SetupAppRunningError=安裝程式偵測到 %1 目前正在執行中。%n%n請先關閉所有執行中的視窗，然後按「確定」繼續，或按「取消」離開。
UninstallAppRunningError=解除安裝程式偵測到 %1 目前正在執行中。%n%n請先關閉所有執行中的視窗，然後按「確定」繼續，或按「取消」離開。

; *** Startup questions
PrivilegesRequiredOverrideTitle=選擇安裝模式
PrivilegesRequiredOverrideInstruction=請選擇安裝模式
PrivilegesRequiredOverrideText1=%1 可以為所有使用者安裝（需要系統管理員權限），或僅為目前使用者安裝。
PrivilegesRequiredOverrideText2=%1 可以僅為目前使用者安裝，或為所有使用者安裝（需要系統管理員權限）。
PrivilegesRequiredOverrideAllUsers=為所有使用者安裝(&A)
PrivilegesRequiredOverrideAllUsersRecommended=為所有使用者安裝（建議）(&A)
PrivilegesRequiredOverrideCurrentUser=僅為目前使用者安裝(&M)
PrivilegesRequiredOverrideCurrentUserRecommended=僅為目前使用者安裝（建議）(&M)

; *** Misc. errors
ErrorCreatingDir=安裝程式無法建立資料夾「%1」
ErrorTooManyFilesInDir=無法在資料夾「%1」建立檔案，因為其中的檔案數量已達上限

; *** Setup common messages
ExitSetupTitle=結束安裝
ExitSetupMessage=安裝尚未完成。如果現在結束，程式將不會被安裝。%n%n您之後可隨時重新執行安裝程式完成安裝。%n%n確定要結束安裝嗎？
AboutSetupMenuItem=關於安裝程式(&A)...
AboutSetupTitle=關於安裝程式
AboutSetupMessage=%1 版本 %2%n%3%n%n%1 首頁:%n%4
AboutSetupNote=
TranslatorNote=

; *** Buttons
ButtonBack=< 上一步(&B)
ButtonNext=下一步(&N) >
ButtonInstall=安裝(&I)
ButtonOK=確定
ButtonCancel=取消
ButtonYes=是(&Y)
ButtonYesToAll=全部皆是(&A)
ButtonNo=否(&N)
ButtonNoToAll=全部皆否(&O)
ButtonFinish=完成(&F)
ButtonBrowse=瀏覽(&B)...
ButtonWizardBrowse=瀏覽(&R)...
ButtonNewFolder=建立新資料夾(&M)

; *** "Select Language" dialog messages
SelectLanguageTitle=選擇安裝語言
SelectLanguageLabel=請選擇安裝過程要使用的語言。

; *** Common wizard text
ClickNext=按「下一步」繼續，或按「取消」結束安裝。
BeveledLabel=
BrowseDialogTitle=瀏覽資料夾
BrowseDialogLabel=請在下方清單選取一個資料夾，然後按「確定」。
NewFolderName=新資料夾

; *** "Welcome" wizard page
WelcomeLabel1=歡迎使用 [name] 安裝精靈
WelcomeLabel2=本精靈將在您的電腦安裝 [name/ver]。%n%n建議您在繼續前先關閉其他應用程式。

; *** "Password" wizard page
WizardPassword=密碼
PasswordLabel1=此安裝程式受到密碼保護。
PasswordLabel3=請輸入密碼，然後按「下一步」繼續（密碼區分大小寫）。
PasswordEditLabel=密碼(&P):
IncorrectPassword=您輸入的密碼不正確，請再試一次。

; *** "License Agreement" wizard page
WizardLicense=授權條款
LicenseLabel=繼續安裝前請先閱讀以下重要資訊。
LicenseLabel3=請閱讀以下授權條款。您必須接受此條款才能繼續安裝。
LicenseAccepted=我同意此條款(&A)
LicenseNotAccepted=我不同意此條款(&D)

; *** "Information" wizard pages
WizardInfoBefore=資訊
InfoBeforeLabel=繼續安裝前請先閱讀以下重要資訊。
InfoBeforeClickLabel=準備好繼續安裝時，請按「下一步」。
WizardInfoAfter=資訊
InfoAfterLabel=繼續前請先閱讀以下重要資訊。
InfoAfterClickLabel=準備好繼續時，請按「下一步」。

; *** "User Information" wizard page
WizardUserInfo=使用者資訊
UserInfoDesc=請輸入您的資訊。
UserInfoName=使用者名稱(&U):
UserInfoOrg=組織(&O):
UserInfoSerial=序號(&S):
UserInfoNameRequired=您必須輸入名稱。

; *** "Select Destination Location" wizard page
WizardSelectDir=選擇安裝資料夾
SelectDirDesc=您想將 [name] 安裝在哪裡？
SelectDirLabel3=安裝程式會將 [name] 安裝到下列資料夾。
SelectDirBrowseLabel=請按「下一步」繼續。如果想選擇其他資料夾，請按「瀏覽」。
DiskSpaceGBLabel=至少需要 [gb] GB 可用磁碟空間。
DiskSpaceMBLabel=至少需要 [mb] MB 可用磁碟空間。
CannotInstallToNetworkDrive=安裝程式無法安裝至網路磁碟機。
CannotInstallToUNCPath=安裝程式無法安裝至 UNC 路徑。
InvalidPath=請輸入包含磁碟機代號的完整路徑，例如:%n%nC:\APP%n%n或如下格式的 UNC 路徑:%n%n\\server\share
InvalidDrive=您選擇的磁碟機或 UNC 共用位置不存在或無法存取，請重新選擇。
DiskSpaceWarningTitle=磁碟空間不足
DiskSpaceWarning=安裝至少需要 %1 KB 可用空間，但您選取的磁碟機目前僅剩 %2 KB 可用。%n%n仍要繼續安裝嗎？
DirNameTooLong=資料夾名稱或路徑過長。
InvalidDirName=資料夾名稱無效。
BadDirName32=資料夾名稱不可包含以下任何字元:%n%n%1
DirExistsTitle=資料夾已存在
DirExists=資料夾:%n%n%1%n%n已經存在。仍要安裝到該資料夾嗎？
DirDoesntExistTitle=資料夾不存在
DirDoesntExist=資料夾:%n%n%1%n%n目前不存在。要建立該資料夾嗎？

; *** "Select Components" wizard page
WizardSelectComponents=選擇元件
SelectComponentsDesc=要安裝哪些元件？
SelectComponentsLabel2=請勾選您要安裝的元件，取消勾選不需要的元件，準備好後按「下一步」繼續。
FullInstallation=完整安裝
CompactInstallation=精簡安裝
CustomInstallation=自訂安裝
NoUninstallWarningTitle=元件已存在
NoUninstallWarning=安裝程式偵測到您的電腦已安裝下列元件:%n%n%1%n%n取消勾選並不會將其解除安裝。%n%n仍要繼續嗎？
ComponentSize1=%1 KB
ComponentSize2=%1 MB
ComponentsDiskSpaceGBLabel=目前選擇至少需要 [gb] GB 磁碟空間。
ComponentsDiskSpaceMBLabel=目前選擇至少需要 [mb] MB 磁碟空間。

; *** "Select Additional Tasks" wizard page
WizardSelectTasks=選擇額外工作
SelectTasksDesc=還要執行哪些額外項目？
SelectTasksLabel2=請選擇安裝 [name] 時一併執行的額外項目，然後按「下一步」。

; *** "Select Start Menu Folder" wizard page
WizardSelectProgramGroup=選擇開始功能表資料夾
SelectStartMenuFolderDesc=安裝程式應將程式捷徑放在哪裡？
SelectStartMenuFolderLabel3=安裝程式會在下列「開始」功能表資料夾建立捷徑。
SelectStartMenuFolderBrowseLabel=請按「下一步」繼續。如果想選擇其他資料夾，請按「瀏覽」。
MustEnterGroupName=您必須輸入資料夾名稱。
GroupNameTooLong=資料夾名稱或路徑過長。
InvalidGroupName=資料夾名稱無效。
BadGroupName=資料夾名稱不可包含以下任何字元:%n%n%1
NoProgramGroupCheck2=不要建立開始功能表資料夾(&D)

; *** "Ready to Install" wizard page
WizardReady=準備安裝
ReadyLabel1=安裝程式已準備好在您的電腦安裝 [name]。
ReadyLabel2a=按「安裝」開始安裝，或按「上一步」檢視或變更設定。
ReadyLabel2b=請按「安裝」繼續。
ReadyMemoUserInfo=使用者資訊:
ReadyMemoDir=安裝資料夾:
ReadyMemoType=安裝類型:
ReadyMemoComponents=已選元件:
ReadyMemoGroup=開始功能表資料夾:
ReadyMemoTasks=額外項目:

; *** TDownloadWizardPage wizard page and DownloadTemporaryFile
DownloadingLabel2=正在下載檔案...
ButtonStopDownload=停止下載(&S)
StopDownload=確定要停止下載嗎？
ErrorDownloadAborted=下載已中止
ErrorDownloadFailed=下載失敗: %1 %2
ErrorDownloadSizeFailed=取得檔案大小失敗: %1 %2
ErrorProgress=無效進度: %1 / %2
ErrorFileSize=檔案大小不符: 預期為 %1，實際為 %2

; *** TExtractionWizardPage wizard page and ExtractArchive
ExtractingLabel=正在解壓縮檔案...
ButtonStopExtraction=停止解壓縮(&S)
StopExtraction=確定要停止解壓縮嗎？
ErrorExtractionAborted=解壓縮已中止
ErrorExtractionFailed=解壓縮失敗: %1

; *** Archive extraction failure details
ArchiveIncorrectPassword=密碼不正確
ArchiveIsCorrupted=壓縮檔已損毀
ArchiveUnsupportedFormat=不支援的壓縮格式

; *** "Preparing to Install" wizard page
WizardPreparing=正在準備安裝
PreparingDesc=安裝程式正在準備在您的電腦安裝 [name]。
PreviousInstallNotCompleted=前一個程式的安裝或移除尚未完成，您需要重新啟動電腦才能完成該動作。%n%n重新啟動電腦後，請再執行安裝程式以完成 [name] 的安裝。
CannotContinue=安裝無法繼續，請按「取消」離開。
ApplicationsFound=下列應用程式正在使用安裝程式需要更新的檔案。建議您允許安裝程式自動關閉這些程式。
ApplicationsFound2=下列應用程式正在使用安裝程式需要更新的檔案。建議您允許安裝程式自動關閉這些程式，安裝完成後將嘗試重新啟動它們。
CloseApplications=自動關閉這些應用程式(&A)
DontCloseApplications=不要關閉這些應用程式(&D)
ErrorCloseApplications=安裝程式無法自動關閉所有應用程式，建議您手動關閉相關程式後再繼續。
PrepareToInstallNeedsRestart=安裝程式必須重新啟動電腦。重開機後請再執行安裝程式完成 [name] 的安裝。%n%n現在要重新啟動嗎？

; *** "Installing" wizard page
WizardInstalling=正在安裝
InstallingLabel=正在將 [name] 安裝到您的電腦，請稍候。

; *** "Setup Completed" wizard page
FinishedHeadingLabel=完成 [name] 安裝精靈
FinishedLabelNoIcons=已完成在您的電腦安裝 [name]。
FinishedLabel=已完成在您的電腦安裝 [name]，您可透過已建立的捷徑啟動程式。
ClickFinish=按「完成」離開安裝精靈。
FinishedRestartLabel=必須重新啟動電腦才能完成 [name] 的安裝。現在要重新啟動嗎？
FinishedRestartMessage=必須重新啟動電腦才能完成 [name] 的安裝。%n%n現在要重新啟動嗎？
ShowReadmeCheck=是，我要檢視讀我檔案
YesRadio=是，立即重新啟動電腦(&Y)
NoRadio=否，我稍後再自行重新啟動(&N)
RunEntryExec=執行 %1
RunEntryShellExec=檢視 %1

; *** "Setup Needs the Next Disk" stuff
ChangeDiskTitle=安裝程式需要下一片磁碟
SelectDiskLabel2=請插入磁碟 %1 並按「確定」。%n%n如果檔案位於其他資料夾，請輸入正確路徑或按「瀏覽」。
PathLabel=路徑(&P):
FileNotInDir2=在「%2」中找不到檔案「%1」。請插入正確磁碟或選取其他資料夾。
SelectDirectoryLabel=請指定下一片磁碟的位置。

; *** Installation phase messages
SetupAborted=安裝未完成。%n%n請修正問題後重新執行安裝程式。
AbortRetryIgnoreSelectAction=請選擇操作
AbortRetryIgnoreRetry=重試(&T)
AbortRetryIgnoreIgnore=忽略錯誤並繼續(&I)
AbortRetryIgnoreCancel=取消安裝
RetryCancelSelectAction=請選擇操作
RetryCancelRetry=重試(&T)
RetryCancelCancel=取消

; *** Installation status messages
StatusClosingApplications=正在關閉應用程式...
StatusCreateDirs=正在建立資料夾...
StatusExtractFiles=正在解壓縮檔案...
StatusDownloadFiles=正在下載檔案...
StatusCreateIcons=正在建立捷徑...
StatusCreateIniEntries=正在建立 INI 設定...
StatusCreateRegistryEntries=正在寫入登錄檔項目...
StatusRegisterFiles=正在註冊檔案...
StatusSavingUninstall=正在儲存解除安裝資訊...
StatusRunProgram=正在完成安裝...
StatusRestartingApplications=正在重新啟動應用程式...
StatusRollback=正在還原變更...

; *** Misc. errors
ErrorInternal2=內部錯誤: %1
ErrorFunctionFailedNoCode=%1 失敗
ErrorFunctionFailed=%1 失敗；錯誤代碼 %2
ErrorFunctionFailedWithMessage=%1 失敗；錯誤代碼 %2。%n%3
ErrorExecutingProgram=無法執行檔案:%n%1

; *** Registry errors
ErrorRegOpenKey=開啟登錄機碼失敗:%n%1\%2
ErrorRegCreateKey=建立登錄機碼失敗:%n%1\%2
ErrorRegWriteKey=寫入登錄機碼失敗:%n%1\%2

; *** INI errors
ErrorIniEntry=在檔案「%1」建立 INI 項目時發生錯誤。

; *** File copying errors
FileAbortRetryIgnoreSkipNotRecommended=略過此檔案（不建議）
FileAbortRetryIgnoreIgnoreNotRecommended=忽略錯誤並繼續（不建議）
SourceIsCorrupted=來源檔案已損毀
SourceDoesntExist=來源檔案「%1」不存在
SourceVerificationFailed=來源檔案驗證失敗: %1
VerificationSignatureDoesntExist=簽章檔案「%1」不存在
VerificationSignatureInvalid=簽章檔案「%1」無效
VerificationKeyNotFound=簽章檔案「%1」使用未知金鑰
VerificationFileNameIncorrect=檔案名稱不正確
VerificationFileTagIncorrect=檔案標籤不正確
VerificationFileSizeIncorrect=檔案大小不正確
VerificationFileHashIncorrect=檔案雜湊不正確
ExistingFileReadOnly2=既有檔案設為唯讀，無法取代。
ExistingFileReadOnlyRetry=移除唯讀屬性並重試(&R)
ExistingFileReadOnlyKeepExisting=保留既有檔案(&K)
ErrorReadingExistingDest=讀取既有檔案時發生錯誤:
FileExistsSelectAction=請選擇操作
FileExists2=檔案已存在。
FileExistsOverwriteExisting=覆寫既有檔案(&O)
FileExistsKeepExisting=保留既有檔案(&K)
FileExistsOverwriteOrKeepAll=後續衝突皆套用相同處理(&D)
ExistingFileNewerSelectAction=請選擇操作
ExistingFileNewer2=既有檔案比安裝程式要安裝的版本更新。
ExistingFileNewerOverwriteExisting=覆寫既有檔案(&O)
ExistingFileNewerKeepExisting=保留既有檔案（建議）(&K)
ExistingFileNewerOverwriteOrKeepAll=後續衝突皆套用相同處理(&D)
ErrorChangingAttr=變更既有檔案屬性時發生錯誤:
ErrorCreatingTemp=在目標資料夾建立暫存檔時發生錯誤:
ErrorReadingSource=讀取來源檔案時發生錯誤:
ErrorCopying=複製檔案時發生錯誤:
ErrorDownloading=下載檔案時發生錯誤:
ErrorExtracting=解壓縮檔案時發生錯誤:
ErrorReplacingExistingFile=取代既有檔案時發生錯誤:
ErrorRestartReplace=RestartReplace 失敗:
ErrorRenamingTemp=重新命名目標資料夾檔案時發生錯誤:
ErrorRegisterServer=無法註冊 DLL/OCX: %1
ErrorRegSvr32Failed=RegSvr32 失敗，結束代碼 %1
ErrorRegisterTypeLib=無法註冊型別程式庫: %1

; *** Uninstall display name markings
UninstallDisplayNameMark=%1 (%2)
UninstallDisplayNameMarks=%1 (%2, %3)
UninstallDisplayNameMark32Bit=32 位元
UninstallDisplayNameMark64Bit=64 位元
UninstallDisplayNameMarkAllUsers=所有使用者
UninstallDisplayNameMarkCurrentUser=目前使用者

; *** Post-installation errors
ErrorOpeningReadme=開啟讀我檔案時發生錯誤。
ErrorRestartingComputer=安裝程式無法重新啟動電腦，請手動重新啟動。

; *** Uninstaller messages
UninstallNotFound=檔案「%1」不存在，無法解除安裝。
UninstallOpenError=無法開啟檔案「%1」，無法解除安裝
UninstallUnsupportedVer=此版本的解除安裝程式無法辨識「%1」的記錄格式，無法解除安裝
UninstallUnknownEntry=解除安裝記錄中出現未知項目 (%1)
ConfirmUninstall=您確定要完全移除 %1 及其所有元件嗎？
UninstallOnlyOnWin64=此程式僅能在 64 位元 Windows 上解除安裝。
OnlyAdminCanUninstall=此程式必須由具有系統管理員權限的使用者解除安裝。
UninstallStatusLabel=正在從您的電腦移除 %1，請稍候。
UninstalledAll=已成功從您的電腦移除 %1。
UninstalledMost=已完成 %1 解除安裝。%n%n部分項目無法自動移除，您可手動刪除。
UninstalledAndNeedsRestart=必須重新啟動電腦才能完成 %1 的移除。%n%n現在要重新啟動嗎？
UninstallDataCorrupted=「%1」檔案已損毀，無法解除安裝

; *** Uninstallation phase messages
ConfirmDeleteSharedFileTitle=要移除共用檔案嗎？
ConfirmDeleteSharedFile2=系統顯示已無其他程式使用下列共用檔案，是否要由解除安裝程式移除？%n%n若仍有程式需要此檔案卻被移除，該程式可能無法正常運作；如果不確定，請選「否」，保留此檔案不會造成問題。
SharedFileNameLabel=檔案名稱:
SharedFileLocationLabel=位置:
WizardUninstalling=解除安裝狀態
StatusUninstalling=正在解除安裝 %1...

; *** Shutdown block reasons
ShutdownBlockReasonInstallingApp=正在安裝 %1。
ShutdownBlockReasonUninstallingApp=正在解除安裝 %1。

[CustomMessages]

NameAndVersion=%1 版本 %2
AdditionalIcons=其他捷徑:
CreateDesktopIcon=建立桌面捷徑(&D)
CreateQuickLaunchIcon=建立快速啟動捷徑(&Q)
ProgramOnTheWeb=%1 網站
UninstallProgram=解除安裝 %1
LaunchProgram=啟動 %1
AssocFileExtension=將 %1 與 %2 副檔名關聯(&A)
AssocingFileExtension=正在將 %1 與 %2 副檔名關聯...
AutoStartProgramGroupDescription=啟動:
AutoStartProgram=自動啟動 %1
AddonHostProgramNotFound=在您選擇的資料夾找不到 %1。%n%n仍要繼續嗎？
