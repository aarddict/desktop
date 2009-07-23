[Setup]
AppName=Aard Dictionary
AppVerName=Aard Dictionary 0.7.5
DefaultDirName={pf}\Aard Dictionary
DefaultGroupName=Accessories
UninstallDisplayIcon={app}\aarddict.exe
Compression=lzma
SolidCompression=yes
OutputDir=..\winsetup

[Files]
Source: "..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Aard Dictionary"; Filename: "{app}\run.exe"
