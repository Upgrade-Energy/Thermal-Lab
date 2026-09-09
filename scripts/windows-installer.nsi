Unicode True
!include "MUI2.nsh"
!include "LogicLib.nsh"
!include "x64.nsh"
!include "WinVer.nsh"
Name "@APP_NAME@"
OutFile "@OUTFILE@"
InstallDir "$LOCALAPPDATA\Programs\UpgradeEnergy\@APP_ID@"
RequestExecutionLevel user
SetCompressor /SOLID lzma
ShowInstDetails show
BrandingText "Upgrade Energy · @APP_NAME@ @VERSION@"
Var Gate
Var VersionDir
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

!macro AcquireGate PREFIX
Function ${PREFIX}.onInit
  SetShellVarContext current
  SetRegView 64
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "@APP_NAME@ requires Windows x64."
    SetErrorLevel 1
    Abort
  ${EndIf}
  ${IfNot} ${AtLeastWin10}
    MessageBox MB_ICONSTOP "@APP_NAME@ requires Windows 10 or 11."
    SetErrorLevel 1
    Abort
  ${EndIf}
  System::Call 'kernel32::CreateMutexW(p 0, i 0, w "Local\UpgradeEnergy.@APP_ID@.InstallGate") p .r0'
  StrCpy $Gate $0
  ${If} $Gate == 0
    SetErrorLevel 2
    Abort "Cannot verify installation lock."
  ${EndIf}
  System::Call 'kernel32::WaitForSingleObject(p r0, i 0) i .r1'
  ${If} $1 != 0
  ${AndIf} $1 != 128
    MessageBox MB_ICONSTOP "Another @APP_NAME@ installer is running."
    SetErrorLevel 2
    Abort
  ${EndIf}
  System::Call 'kernel32::OpenMutexW(i 0x100000, i 0, w "Local\UpgradeEnergy.@APP_ID@.Running") p .r1 ?e'
  Pop $2
  ${If} $1 != 0
    System::Call 'kernel32::CloseHandle(p r1)'
    MessageBox MB_ICONEXCLAMATION "Close every @APP_NAME@ window and its background service, then run this installer again. Active work will not be interrupted." /SD IDOK
    SetErrorLevel 3
    Abort
  ${ElseIf} $2 != 2
    MessageBox MB_ICONSTOP "Cannot verify whether @APP_NAME@ is running." /SD IDOK
    SetErrorLevel 3
    Abort
  ${EndIf}
FunctionEnd
Function ${PREFIX}.onGUIEnd
  StrCpy $0 $Gate
  System::Call 'kernel32::ReleaseMutex(p r0)'
  System::Call 'kernel32::CloseHandle(p r0)'
FunctionEnd
!macroend
!insertmacro AcquireGate ""
!insertmacro AcquireGate "un"

Section "Install"
  CreateDirectory "$INSTDIR\versions"
  ; Reserve a fresh directory even when reinstalling the same build. An open
  ; updater may still use the previous runtime; never overwrite its files.
  ClearErrors
  GetTempFileName $VersionDir "$INSTDIR\versions"
  ${If} ${Errors}
    SetErrorLevel 4
    Abort "Could not reserve an installation directory."
  ${EndIf}
  Delete $VersionDir
  SetOutPath $VersionDir
  ClearErrors
  File /r "@PAYLOAD@/*"
  ${If} ${Errors}
    MessageBox MB_ICONSTOP "Files could not be installed. The previous version remains selected." /SD IDOK
    SetErrorLevel 4
    Abort
  ${EndIf}
  DetailPrint "Verifying the bundled runtime and application before activation..."
  nsExec::ExecToLog '"$VersionDir\runtime\python.exe" "$VersionDir\scripts\installer_smoke.py" --activate "$INSTDIR"'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONSTOP "Installation validation failed. The previous version and all recordings are retained. Open installation details for the error." /SD IDOK
    SetErrorLevel 5
    Abort
  ${EndIf}
  SetOutPath "$INSTDIR"
  FileOpen $0 "$INSTDIR\Launch.vbs.tmp" w
  FileWrite $0 'Option Explicit$\r$\nDim fs, base, stream, version, expression, app, mode, shell$\r$\n'
  FileWrite $0 'Set fs = CreateObject("Scripting.FileSystemObject")$\r$\nbase = fs.GetParentFolderName(WScript.ScriptFullName)$\r$\n'
  FileWrite $0 'Set stream = fs.OpenTextFile(fs.BuildPath(base, "current.txt"), 1)$\r$\nversion = Trim(stream.ReadAll)$\r$\nstream.Close$\r$\n'
  FileWrite $0 'Set expression = New RegExp$\r$\nexpression.Pattern = "^[0-9A-Za-z.-]+$$"$\r$\nIf Not expression.Test(version) Then WScript.Quit 1$\r$\n'
  FileWrite $0 'app = fs.BuildPath(fs.BuildPath(base, "versions"), version)$\r$\nmode = "app"$\r$\nIf WScript.Arguments.Count > 0 Then mode = WScript.Arguments(0)$\r$\n'
  FileWrite $0 'If mode <> "app" And mode <> "updates" And mode <> "service" And mode <> "review" Then WScript.Quit 1$\r$\n'
  FileWrite $0 'Set shell = CreateObject("WScript.Shell")$\r$\nshell.CurrentDirectory = app$\r$\nshell.Run Chr(34) & fs.BuildPath(app, "runtime\pythonw.exe") & Chr(34) & " " & Chr(34) & fs.BuildPath(app, "launch_installed.py") & Chr(34) & " " & mode, 1, False$\r$\n'
  FileClose $0
  System::Call 'kernel32::MoveFileExW(w "$INSTDIR\Launch.vbs.tmp", w "$INSTDIR\Launch.vbs", i 9) i .r0'
  ${If} $0 == 0
    SetErrorLevel 6
    Abort "Could not activate the application launcher. Run setup again."
  ${EndIf}
  CreateDirectory "$SMPROGRAMS\Upgrade Energy"
  CreateShortCut "$DESKTOP\@APP_NAME@.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\Launch.vbs" app'
  CreateShortCut "$SMPROGRAMS\Upgrade Energy\@APP_NAME@.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\Launch.vbs" app'
  CreateShortCut "$SMPROGRAMS\Upgrade Energy\@APP_NAME@ - Check for updates.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\Launch.vbs" updates'
  !if "@APP_ID@" == "ThermalLab"
    CreateShortCut "$SMPROGRAMS\Upgrade Energy\Thermal Lab - Power Lab service.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\Launch.vbs" service'
    CreateShortCut "$SMPROGRAMS\Upgrade Energy\Thermal Lab - Review recordings.lnk" "$SYSDIR\wscript.exe" '"$INSTDIR\Launch.vbs" review'
  !endif
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@" "DisplayName" "@APP_NAME@"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@" "DisplayVersion" "@VERSION@"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@" "Publisher" "Upgrade Energy"
  WriteRegStr HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@" "UninstallString" '$\"$INSTDIR\Uninstall.exe$\"'
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@" "NoModify" 1
  WriteRegDWORD HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@" "NoRepair" 1
SectionEnd

Section "Uninstall"
  Delete "$DESKTOP\@APP_NAME@.lnk"
  Delete "$SMPROGRAMS\Upgrade Energy\@APP_NAME@.lnk"
  Delete "$SMPROGRAMS\Upgrade Energy\@APP_NAME@ - Check for updates.lnk"
  !if "@APP_ID@" == "ThermalLab"
    Delete "$SMPROGRAMS\Upgrade Energy\Thermal Lab - Power Lab service.lnk"
    Delete "$SMPROGRAMS\Upgrade Energy\Thermal Lab - Review recordings.lnk"
  !endif
  RMDir /r "$INSTDIR\versions"
  Delete "$INSTDIR\Launch.vbs"
  Delete "$INSTDIR\current.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  DeleteRegKey HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\UpgradeEnergy@APP_ID@"
  DetailPrint "Settings, camera layouts, recordings and saved GitHub access have been retained."
SectionEnd
