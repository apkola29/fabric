# Shared helpers for deploy.ps1 (dot-source this file).

function Get-NextOccurrence {
    <#
    .SYNOPSIS
        Next wall-clock occurrence of a time of day in a time zone, as a DateTimeOffset.
    .DESCRIPTION
        Used to compute the first start time of an Azure Automation schedule. Handles daylight
        saving: a local time that does not exist (spring-forward gap) moves forward one hour, and the
        UTC offset is the one in effect on the chosen date.
    .PARAMETER TimeZoneId
        IANA ID (America/Chicago) or Windows ID (Central Standard Time), whichever the host supports.
    .PARAMETER TimeOfDay
        24-hour time, HH:mm.
    .PARAMETER MinLeadMinutes
        The result is at least this many minutes in the future (Automation requires a future start).
    #>
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)] [string] $TimeZoneId,
        [Parameter(Mandatory)] [ValidatePattern('^([01]\d|2[0-3]):[0-5]\d$')] [string] $TimeOfDay,
        [datetime] $NowUtc = [datetime]::UtcNow,
        [int] $MinLeadMinutes = 10
    )

    $zone = [TimeZoneInfo]::FindSystemTimeZoneById($TimeZoneId)
    $time = [timespan]::ParseExact($TimeOfDay, 'hh\:mm', [cultureinfo]::InvariantCulture)
    $utcNow = [datetime]::SpecifyKind($NowUtc, [DateTimeKind]::Utc)
    $localNow = [TimeZoneInfo]::ConvertTimeFromUtc($utcNow, $zone)

    $candidate = [datetime]::SpecifyKind($localNow.Date.Add($time), [DateTimeKind]::Unspecified)
    $earliest = $utcNow.AddMinutes($MinLeadMinutes)

    for ($i = 0; $i -lt 3; $i++) {
        $probe = $candidate
        while ($zone.IsInvalidTime($probe)) { $probe = $probe.AddHours(1) }

        # A fall-back hour happens twice. ConvertTimeToUtc assumes the second (standard-time) one, which can
        # skip a first occurrence that still qualifies, so consider both offsets and take the earliest.
        $offsets = if ($zone.IsAmbiguousTime($probe)) { $zone.GetAmbiguousTimeOffsets($probe) } else { @($zone.GetUtcOffset($probe)) }
        $best = $null
        foreach ($offset in ($offsets | Sort-Object -Descending)) {
            $candidateUtc = [datetime]::SpecifyKind($probe - $offset, [DateTimeKind]::Utc)
            if ($candidateUtc -ge $earliest) { $best = [DateTimeOffset]::new($probe, $offset); break }
        }
        if ($best) { return $best }
        $candidate = $candidate.AddDays(1)
    }
    throw "Could not compute the next occurrence of $TimeOfDay in $TimeZoneId."
}

function Format-ScheduleTime {
    param([Parameter(Mandatory)] [DateTimeOffset] $Value)
    return $Value.ToString("yyyy-MM-dd'T'HH:mm:sszzz", [cultureinfo]::InvariantCulture)
}

function Get-DeterministicGuid {
    <# Stable GUID from a string, so re-running a deployment targets the same job-schedule link. #>
    param([Parameter(Mandatory)] [string] $Text)
    $md5 = [System.Security.Cryptography.MD5]::Create()
    try {
        $bytes = $md5.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Text))
    }
    finally { $md5.Dispose() }
    return [guid]::new($bytes)
}
