#Requires -Modules @{ ModuleName = 'Pester'; ModuleVersion = '5.0.0' }

BeforeAll {
    . (Join-Path $PSScriptRoot '..\scripts\common.ps1')
}

Describe 'Get-NextOccurrence' {
    It 'returns tonight when the time is still ahead (UTC)' {
        $now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'UTC' -TimeOfDay '23:30' -NowUtc $now
        $r.UtcDateTime | Should -Be ([datetime]::new(2026, 10, 15, 23, 30, 0, [DateTimeKind]::Utc))
    }

    It 'rolls to tomorrow when the time has passed' {
        $now = [datetime]::new(2026, 10, 15, 20, 0, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'UTC' -TimeOfDay '00:00' -NowUtc $now
        $r.UtcDateTime | Should -Be ([datetime]::new(2026, 10, 16, 0, 0, 0, [DateTimeKind]::Utc))
    }

    It 'skips an occurrence that is closer than the minimum lead time' {
        $now = [datetime]::new(2026, 10, 15, 23, 55, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'UTC' -TimeOfDay '00:00' -NowUtc $now -MinLeadMinutes 10
        $r.UtcDateTime | Should -Be ([datetime]::new(2026, 10, 17, 0, 0, 0, [DateTimeKind]::Utc))
    }

    It 'accepts an occurrence that is just far enough ahead' {
        $now = [datetime]::new(2026, 10, 15, 23, 55, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'UTC' -TimeOfDay '00:00' -NowUtc $now -MinLeadMinutes 3
        $r.UtcDateTime | Should -Be ([datetime]::new(2026, 10, 16, 0, 0, 0, [DateTimeKind]::Utc))
    }

    It 'uses the daylight offset in summer and standard offset in winter (America/Chicago)' {
        $summer = Get-NextOccurrence -TimeZoneId 'America/Chicago' -TimeOfDay '00:00' -NowUtc ([datetime]::new(2026, 7, 1, 12, 0, 0, [DateTimeKind]::Utc))
        $summer.Offset.TotalHours | Should -Be -5
        $summer.UtcDateTime.Hour | Should -Be 5

        $winter = Get-NextOccurrence -TimeZoneId 'America/Chicago' -TimeOfDay '00:00' -NowUtc ([datetime]::new(2026, 12, 1, 12, 0, 0, [DateTimeKind]::Utc))
        $winter.Offset.TotalHours | Should -Be -6
        $winter.UtcDateTime.Hour | Should -Be 6
    }

    It 'moves a nonexistent spring-forward time forward an hour (America/Chicago, 2026-03-08 02:30)' {
        $now = [datetime]::new(2026, 3, 8, 0, 0, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'America/Chicago' -TimeOfDay '02:30' -NowUtc $now
        $r.DateTime.ToString('yyyy-MM-dd HH:mm') | Should -Be '2026-03-08 03:30'
    }

    It 'picks the FIRST occurrence of an ambiguous fall-back time when it still qualifies (America/Chicago, 2026-11-01 01:30)' {
        $now = [datetime]::new(2026, 11, 1, 5, 0, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'America/Chicago' -TimeOfDay '01:30' -NowUtc $now
        $r.UtcDateTime | Should -Be ([datetime]::new(2026, 11, 1, 6, 30, 0, [DateTimeKind]::Utc))
        $r.Offset.TotalHours | Should -Be -5
    }

    It 'falls to the SECOND occurrence of an ambiguous time when only it is far enough ahead' {
        $now = [datetime]::new(2026, 11, 1, 6, 25, 0, [DateTimeKind]::Utc)
        $r = Get-NextOccurrence -TimeZoneId 'America/Chicago' -TimeOfDay '01:30' -NowUtc $now
        $r.UtcDateTime | Should -Be ([datetime]::new(2026, 11, 1, 7, 30, 0, [DateTimeKind]::Utc))
        $r.Offset.TotalHours | Should -Be -6
    }

    It 'rejects malformed times' {
        { Get-NextOccurrence -TimeZoneId 'UTC' -TimeOfDay '24:00' } | Should -Throw
        { Get-NextOccurrence -TimeZoneId 'UTC' -TimeOfDay '9:5' } | Should -Throw
    }

    It 'rejects unknown time zones' {
        { Get-NextOccurrence -TimeZoneId 'Not/AZone' -TimeOfDay '00:00' } | Should -Throw
    }
}

Describe 'Format-ScheduleTime' {
    It 'renders an ISO 8601 timestamp with offset' {
        $v = [DateTimeOffset]::new(2026, 10, 16, 0, 0, 0, [timespan]::FromHours(-5))
        Format-ScheduleTime $v | Should -Be '2026-10-16T00:00:00-05:00'
    }
}

Describe 'Get-DeterministicGuid' {
    It 'is stable for the same input and different for different input' {
        (Get-DeterministicGuid 'a/b') | Should -Be (Get-DeterministicGuid 'a/b')
        (Get-DeterministicGuid 'a/b') | Should -Not -Be (Get-DeterministicGuid 'a/c')
    }
}
