[Setup]
AppName=Aard Dict
AppVerName=Aard Dict 0.7.0
DefaultDirName={pf}\Aard Dict
DefaultGroupName=Accessories
UninstallDisplayIcon={app}\aarddict.exe
Compression=lzma
SolidCompression=yes
OutputDir=..\winsetup

[Files]
Source: "..\dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Aard Dict"; Filename: "{app}\run.exe"
