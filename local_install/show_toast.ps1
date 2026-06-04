# PowerShell native Toast notifier for Bank Deposit Interest System
# Uses Windows.UI.Notifications API — built into Windows 10/11.
# NO external modules, NO Python wheels, NO internet — 100% free & local.

param(
    [Parameter(Mandatory=$true)][string]$Title,
    [Parameter(Mandatory=$true)][string]$Line1,
    [Parameter(Mandatory=$true)][string]$Line2,
    [Parameter(Mandatory=$true)][string]$Line3,
    [string]$LauncherPath = "",
    [string]$NotificationId = ""
)

try {
    Add-Type -AssemblyName Windows.Data
    Add-Type -AssemblyName Windows.UI
    [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
    [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType=WindowsRuntime] | Out-Null
    [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom, ContentType=WindowsRuntime] | Out-Null

    $appId = "BankDepositInterestSystem"

    # Escape XML-sensitive characters in user input
    function Escape-Xml([string]$s) {
        if ($null -eq $s) { return "" }
        return $s.Replace('&','&amp;').Replace('<','&lt;').Replace('>','&gt;').Replace('"','&quot;')
    }

    $eTitle = Escape-Xml $Title
    $eLine1 = Escape-Xml $Line1
    $eLine2 = Escape-Xml $Line2
    $eLine3 = Escape-Xml $Line3
    $eLauncher = Escape-Xml $LauncherPath
    $eId = Escape-Xml $NotificationId

    # scenario="reminder" makes the toast sticky until user interacts
    $xmlString = @"
<toast scenario="reminder" duration="long" activationType="protocol" launch="bankdeposit:open?nid=$eId">
  <visual>
    <binding template="ToastGeneric">
      <text>$eTitle</text>
      <text>$eLine1</text>
      <text>$eLine2</text>
      <text>$eLine3</text>
    </binding>
  </visual>
  <actions>
    <action content="فتح الوديعة" activationType="protocol" arguments="bankdeposit:open?nid=$eId"/>
    <action content="تم القراءة" activationType="background" arguments="read:$eId"/>
  </actions>
  <audio src="ms-winsoundevent:Notification.Reminder"/>
</toast>
"@

    $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
    $xml.LoadXml($xmlString)

    $toast = New-Object Windows.UI.Notifications.ToastNotification $xml

    $notifier = [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId)
    $notifier.Show($toast)
    exit 0
}
catch {
    # Last-resort fallback: BalloonTip (always works on Windows even without UWP)
    try {
        Add-Type -AssemblyName System.Windows.Forms
        $balloon = New-Object System.Windows.Forms.NotifyIcon
        $balloon.Icon = [System.Drawing.SystemIcons]::Information
        $balloon.BalloonTipTitle = "$Title"
        $balloon.BalloonTipText = "$Line1`n$Line2`n$Line3"
        $balloon.Visible = $true
        $balloon.ShowBalloonTip(30000)
        Start-Sleep -Seconds 32
        $balloon.Dispose()
        exit 0
    }
    catch {
        Write-Error "Both UWP toast and balloon tip failed: $_"
        exit 1
    }
}
