#!/bin/bash
# CYBERPUNK NETRUNNER TERMINAL v3
# Endless cinematic terminal experience
# Run: bash cyberpunk.sh

cleanup() { tput cnorm; tput sgr0; clear; exit 0; }
trap cleanup INT TERM

# Colors
R='\e[31m'; G='\e[32m'; Y='\e[33m'; B='\e[34m'; M='\e[35m'; C='\e[36m'
BR='\e[91m'; BG='\e[92m'; BY='\e[93m'; BB='\e[94m'; BM='\e[95m'; BC='\e[96m'
W='\e[97m'; DIM='\e[2m'; BOLD='\e[1m'; RST='\e[0m'

clear; tput civis
cols=$(tput cols)

# ── Utilities ──

hr() {
    local ch="${1:-─}" color="${2:-${DIM}${C}}"
    printf "${color}"
    for ((i = 0; i < cols; i++)); do printf "%s" "$ch"; done
    printf "${RST}\n"
}

glitch() {
    local text="$1" color="$2" iters="${3:-3}"
    local gc='█▓▒░╔╗╚╝║═╬┼▄▀▐▌'
    for ((g = 0; g < iters; g++)); do
        printf '\r'
        for ((i = 0; i < ${#text}; i++)); do
            if ((RANDOM % 3 == 0)); then
                printf "${BR}%s" "${gc:$((RANDOM % ${#gc})):1}"
            else
                printf "${color}%s" "${text:$i:1}"
            fi
        done
        sleep 0.04
    done
    printf "\r${color}%s${RST}\n" "$text"
}

type_out() {
    local text="$1" color="${2:-$G}" speed="${3:-0.02}"
    printf "${color}"
    for ((i = 0; i < ${#text}; i++)); do
        printf "%s" "${text:$i:1}"
        sleep "$speed"
    done
    printf "${RST}"
}

progress() {
    local label="$1" color="$2" width=35 time="${3:-1.0}"
    local steps=20
    local sleep_t
    sleep_t=$(awk "BEGIN{printf \"%.3f\", $time / $steps}")
    for ((i = 0; i <= steps; i++)); do
        local filled=$((i * width / steps))
        local pct=$((i * 100 / steps))
        printf "\r${color}  %-32s ${RST}${color}[" "$label"
        for ((j = 0; j < width; j++)); do
            if ((j <= filled)); then printf "█"; else printf "${DIM}░${RST}${color}"; fi
        done
        printf "] ${W}%3d%%${RST}" "$pct"
        sleep "$sleep_t"
    done
    printf "\r${color}  %-32s ${RST}${color}[" "$label"
    for ((j = 0; j < width; j++)); do printf "█"; done
    printf "] ${BG}DONE${RST}    \n"
}

hexdump_block() {
    local lines="${1:-8}"
    for ((i = 0; i < lines; i++)); do
        printf "  ${DIM}${C}%08x${RST}  " $((0x7f000000 + RANDOM * 16 + i * 16))
        for ((j = 0; j < 16; j++)); do
            if ((RANDOM % 8 == 0)); then
                printf "${BR}%02x${RST} " $((RANDOM % 256))
            else
                printf "${DIM}%02x${RST} " $((RANDOM % 256))
            fi
        done
        printf "\n"
        sleep 0.03
    done
}

spinner() {
    local msg="$1" duration="$2" color="${3:-${DIM}${C}}"
    local frames=('⠋' '⠙' '⠹' '⠸' '⠼' '⠴' '⠦' '⠧' '⠇' '⠏')
    local end=$((SECONDS + duration))
    while ((SECONDS < end)); do
        for f in "${frames[@]}"; do
            printf "\r  ${BM}%s${RST} ${color}%s${RST}" "$f" "$msg"
            sleep 0.08
        done
    done
    printf "\r  ${BG}✓${RST} ${color}%s${RST}\n" "$msg"
}

warning_flash() {
    local msg="$1"
    for ((i = 0; i < 3; i++)); do
        printf "\r  ${BOLD}${BR}⚠  %s  ⚠${RST}" "$msg"
        sleep 0.15
        printf "\r  ${DIM}${R}⚠  %s  ⚠${RST}" "$msg"
        sleep 0.15
    done
    printf "\r  ${BOLD}${BR}⚠  %s  ⚠${RST}\n" "$msg"
}

randhex() { for ((i = 0; i < ${1:-8}; i++)); do printf '%x' $((RANDOM % 16)); done; }
randip() { echo "$((RANDOM%254+1)).$((RANDOM%255)).$((RANDOM%255)).$((RANDOM%254+1))"; }

pick() { local arr=("$@"); echo "${arr[$((RANDOM % ${#arr[@]}))]}"; }

# ── Ambient chatter (short bursts) ──

ambient() {
    local lines="${1:-8}" delay="${2:-1.2}"
    for ((n = 0; n < lines; n++)); do
        case $((RANDOM % 7)) in
            0) printf "  ${DIM}${C}[%s]${RST} ${DIM}RELAY %s → %s // %d bytes${RST}\n" \
                "$(date +%H:%M:%S)" "$(randip)" "$(randip)" $((RANDOM % 32768)) ;;
            1) printf "  ${DIM}${BG}▪${RST} ${DIM}%s${RST}\n" \
                "$(pick "ICE probe deflected" "Quantum tunnel nominal" "Ghost protocol holding" \
                       "Memory scrubber cycle complete" "Backup relay tested OK" \
                       "Proxy chain rotated" "Signal bounce confirmed")" ;;
            2) printf "  ${DIM}${M}◇ FRAG %s${RST}\n" "$(randhex 32)" ;;
            3) printf "  ${DIM}${BY}⟡${RST} ${DIM}Passive scan: %d new hosts on %s/24${RST}\n" \
                $((RANDOM % 12 + 1)) "$(randip)" ;;
            4) printf "  ${DIM}${C}[%s]${RST} ${DIM}heartbeat OK | lat: %dms | jitter: %dms${RST}\n" \
                "$(date +%H:%M:%S)" $((RANDOM % 200 + 20)) $((RANDOM % 15)) ;;
            5) local corps=("arasaka" "militech" "kang-tao" "biotechnica" "petrochem" "trauma-team" "zetatech" "orbital-air")
                printf "  ${DIM}⊙ ${corps[$((RANDOM % ${#corps[@]}))]}.corp DNS: %s.onion${RST}\n" "$(randhex 12)" ;;
            6) printf "  ${DIM}${R}▪${RST} ${DIM}Dropped packet from %s (blacklisted)${RST}\n" "$(randip)" ;;
        esac
        sleep "$(awk "BEGIN{printf \"%.1f\", $delay * (0.5 + ($RANDOM % 10) / 10.0)}")"
    done
}

# ══════════════════════════════════════════
#  DRAMATIC SCENES (randomly selected)
# ══════════════════════════════════════════

scene_portscan() {
    local subnet="$((RANDOM % 200 + 10)).$((RANDOM % 255)).$((RANDOM % 255))"
    local target=$(pick "Arasaka Corp" "Militech Industries" "Kang-Tao Group" "Biotechnica Labs" "Zetatech R&D" "NetWatch HQ" "Petrochem Refinery" "Trauma Team Dispatch")

    echo
    hr "═" "${DIM}${M}"
    printf "${BOLD}${BC}  ◈ NETWORK RECONNAISSANCE${RST}\n\n"

    type_out "  Target acquired: ${target}" "$BY" 0.02; echo
    type_out "  Scanning subnet ${subnet}.0/24..." "$DIM$C" 0.01; echo
    echo
    sleep 0.3

    local services=("SSH-2.0-OpenSSH_9.3" "HTTP/1.1 200 OK" "SMTP 220 mail.corp" "MySQL 8.0.35"
        "RDP [NLA required]" "PostgreSQL 16.1" "MongoDB 7.0 - NOAUTH" "Redis 7.2.3" "Elasticsearch 8.12"
        "HTTPS - TLS 1.3 (corp portal)" "FTP 220 Anonymous OK" "Docker API 2375 EXPOSED"
        "Kubernetes API 6443" "Jenkins 2.434" "Grafana 10.2" "MinIO S3 9000")

    local total=$((RANDOM % 8 + 8))
    local open=0
    local vulns=0
    for ((i = 0; i < total; i++)); do
        local ip="${subnet}.$((RANDOM % 254 + 1))"
        local port=$(pick 22 80 443 3306 5432 8080 8443 6379 9200 27017 21 2375 6443 9000 3000 3389)
        if ((RANDOM % 4 != 0)); then
            local svc="${services[$((RANDOM % ${#services[@]}))]}"
            open=$((open + 1))
            if [[ "$svc" == *"NOAUTH"* || "$svc" == *"EXPOSED"* || "$svc" == *"Anonymous"* ]]; then
                vulns=$((vulns + 1))
                printf "  ${BOLD}${BY}★${RST} ${W}%-15s${RST}:${BY}%-5s${RST} ${BG}OPEN${RST}   ${BOLD}${BY}%s${RST}\n" "$ip" "$port" "$svc"
            else
                printf "  ${BG}●${RST} ${W}%-15s${RST}:${BY}%-5s${RST} ${BG}OPEN${RST}   ${DIM}%s${RST}\n" "$ip" "$port" "$svc"
            fi
        else
            printf "  ${DIM}${R}○${RST} ${DIM}%-15s:%-5s FILTERED${RST}\n" "$ip" "$port"
        fi
        sleep 0.12
    done

    echo
    printf "  ${W}Scan complete:${RST} ${BG}%d open${RST} / ${DIM}%d filtered${RST}" "$open" "$((total - open))"
    if ((vulns > 0)); then
        printf " / ${BOLD}${BY}%d VULNERABLE${RST}" "$vulns"
    fi
    printf "\n"
    sleep 0.5
}

scene_database_raid() {
    local db_type=$(pick "MySQL" "PostgreSQL" "MongoDB" "CockroachDB")
    local db_host="$(randip)"
    local db_name=$(pick "arasaka_hr" "personnel_omega" "project_helix" "exec_comms" "rd_prototype" "finance_offshore" "surveillance_nc")

    echo
    hr "═" "${DIM}${M}"
    printf "${BOLD}${BG}  ◈ DATABASE EXFILTRATION${RST}\n\n"

    type_out "  Connecting to ${db_type} @ ${db_host}..." "$C" 0.02; echo
    sleep 0.4
    printf "  ${BG}✓${RST} Authenticated. Database: ${BOLD}${BY}${db_name}${RST}\n\n"
    sleep 0.3

    # Show tables
    printf "  ${BY}>${RST} ${W}SHOW TABLES;${RST}\n"
    sleep 0.3

    local all_tables=("employees" "salaries" "security_clearances" "blackops_personnel"
        "executive_comms" "biometric_data" "termination_records" "project_assignments"
        "offshore_accounts" "ncpd_payroll" "surveillance_feeds" "implant_defects"
        "soulkiller_subjects" "militech_moles" "blackwall_fragments" "ai_containment_logs"
        "neural_implant_telemetry" "political_leverage" "assassination_contracts")

    # Pick 5-8 random tables
    local num_tables=$((RANDOM % 4 + 5))
    local picked_tables=()
    local used=()
    for ((t = 0; t < num_tables; t++)); do
        while true; do
            local idx=$((RANDOM % ${#all_tables[@]}))
            local already=0
            for u in "${used[@]}"; do [[ "$u" == "$idx" ]] && already=1 && break; done
            if ((already == 0)); then
                used+=("$idx")
                picked_tables+=("${all_tables[$idx]}")
                break
            fi
        done
    done

    printf "  ${DIM}┌────────────────────────────┐${RST}\n"
    for t in "${picked_tables[@]}"; do
        if [[ "$t" == *"blackops"* || "$t" == *"soulkiller"* || "$t" == *"assassination"* || "$t" == *"blackwall"* ]]; then
            printf "  ${DIM}│${RST} ${BOLD}${BY}%-26s${RST} ${DIM}│${RST}\n" "$t"
        else
            printf "  ${DIM}│ %-26s │${RST}\n" "$t"
        fi
        sleep 0.06
    done
    printf "  ${DIM}└────────────────────────────┘${RST}\n\n"
    sleep 0.3

    # Query a juicy table
    local juicy="${picked_tables[$((RANDOM % ${#picked_tables[@]}))]}"
    local row_count=$((RANDOM % 90000 + 500))
    printf "  ${BY}>${RST} ${W}SELECT COUNT(*) FROM ${juicy};${RST}\n"
    sleep 0.2
    printf "  ${DIM}→${RST} ${W}%s${RST} rows\n\n" "$(printf '%d' $row_count | sed ':a;s/\B[0-9]\{3\}\>/,&/;ta')"
    sleep 0.3

    # Show some actual rows
    printf "  ${BY}>${RST} ${W}SELECT * FROM ${juicy} LIMIT 5;${RST}\n"
    sleep 0.4

    # Generate contextual fake data based on table name
    local names=("Tanaka, M." "Volkov, A." "Chen, L." "Okonkwo, E." "Reeves, K." "Park, S." "Silva, R." "Nakamura, H." "[REDACTED]" "Fischer, J.")
    local roles=("Operative" "Researcher" "Handler" "Netrunner" "Enforcer" "Analyst" "Cleaner" "Director" "Asset" "[CLASSIFIED]")
    local clearances=("SIGMA-3" "OMEGA-5" "OMEGA-7" "OMEGA-9" "OMEGA-X" "DELTA-2" "ALPHA-1")

    printf "  ${DIM}┌──────────────────────┬────────────────────┬─────────────┐${RST}\n"
    for ((r = 0; r < 5; r++)); do
        local n="${names[$((RANDOM % ${#names[@]}))]}"
        local ro="${roles[$((RANDOM % ${#roles[@]}))]}"
        local cl="${clearances[$((RANDOM % ${#clearances[@]}))]}"
        if [[ "$cl" == "OMEGA-X" || "$n" == "[REDACTED]" ]]; then
            printf "  ${DIM}│${RST} ${BOLD}${BR}%-20s${RST} ${DIM}│${RST} ${BR}%-18s${RST} ${DIM}│${RST} ${BOLD}${BR}%-11s${RST} ${DIM}│${RST}\n" "$n" "$ro" "$cl"
        else
            printf "  ${DIM}│${RST} ${BY}%-20s${RST} ${DIM}│${RST} ${DIM}%-18s${RST} ${DIM}│${RST} ${M}%-11s${RST} ${DIM}│${RST}\n" "$n" "$ro" "$cl"
        fi
        sleep 0.1
    done
    printf "  ${DIM}└──────────────────────┴────────────────────┴─────────────┘${RST}\n\n"
    sleep 0.4

    # Exfil
    for t in "${picked_tables[@]}"; do
        local sz=$((RANDOM % 500 + 10))
        local unit="KB"
        ((sz > 400)) && sz=$((RANDOM % 50 + 1)) && unit="MB"
        progress "Exfil: ${t} (${sz} ${unit})" "$C" "$(awk "BEGIN{printf \"%.1f\", 0.4 + ($RANDOM % 10) / 10.0}")"
    done

    echo
    printf "  ${BG}✓${RST} ${W}Full database dumped and encrypted.${RST}\n"
    sleep 0.5
}

scene_ice_breach() {
    local targets=("Arasaka Secure Vault" "Militech Black Site" "NetWatch Firewall" "Kang-Tao Weapons Lab" "Biotechnica Gene Vault" "Orbital Air Traffic Control")
    local target=$(pick "${targets[@]}")
    local ice_types=("CERBERUS v4.1 (Adaptive)" "HYDRA v2.0 (Multi-Vector)" "BASILISK (Neural Feedback)" "MINOTAUR v3 (Labyrinth)" "KRAKEN (Deep-Layer)")
    local ice=$(pick "${ice_types[@]}")
    local num_layers=$((RANDOM % 4 + 4))

    echo
    hr "═" "${DIM}${BR}"
    printf "${BOLD}${BR}  ◈ ICE BREACH SEQUENCE${RST}\n\n"

    type_out "  Target: ${target}" "$BY" 0.02; echo
    sleep 0.3

    warning_flash "ICE BARRIER DETECTED"
    echo

    printf "  ${BOLD}${BR}  ┌───────────────────────────────────────────────┐${RST}\n"
    printf "  ${BOLD}${BR}  │   ICE Type:    ${BY}%-33s${BR}│${RST}\n" "$ice"
    printf "  ${BOLD}${BR}  │   Layers:      ${BY}%-33s${BR}│${RST}\n" "$num_layers"
    printf "  ${BOLD}${BR}  │   Threat:      ${W}%-33s${BR}│${RST}\n" "$(pick "Neural feedback on failure" "Trace + counterattack" "Daemon retaliation" "Memory wipe on detection")"
    printf "  ${BOLD}${BR}  └───────────────────────────────────────────────┘${RST}\n\n"
    sleep 0.5

    printf "  ${BM}Deploying ICE breakers...${RST}\n\n"

    local layer_names=("Firewall Matrix" "Behavioral Analysis" "Pattern Recognition" "Encryption Lattice"
        "Honeypot Detection" "Daemon Barrier" "Blackwall Shard" "Polymorphic Maze" "Neural Tripwire"
        "Quantum Lattice" "Fractal Labyrinth")
    local methods=("Brute-force key rotation" "Traffic mimicry" "Polymorphic evasion" "Quantum factoring"
        "Signal spoofing" "Daemon injection" "Zero-day exploit" "Side-channel attack" "Timing oracle"
        "Buffer overflow chain" "Race condition abuse")

    local scare_layer=$((RANDOM % num_layers))
    for ((layer = 0; layer < num_layers; layer++)); do
        printf "  ${DIM}Layer $((layer+1))/${num_layers}:${RST} ${BY}${layer_names[$((layer % ${#layer_names[@]}))]}${RST}\n"
        printf "  ${DIM}Method: ${methods[$((layer % ${#methods[@]}))]}${RST}\n"

        local width=30 steps=15
        local time_ms=$((500 + RANDOM % 900))
        for ((s = 0; s < steps; s++)); do
            local filled=$((s * width / steps))
            local pct=$((s * 100 / steps))
            printf "\r  ${BC}  ["
            for ((j = 0; j < width; j++)); do
                if ((j <= filled)); then printf "▓"; else printf "${DIM}░${RST}${BC}"; fi
            done
            printf "]${RST} ${W}%3d%%${RST}" "$pct"

            if ((layer == scare_layer && s == 9)); then
                printf "\r  ${BOLD}${BR}  [▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓▓░░░░░░░░░░░░] ALERT!${RST}"
                sleep 0.3
                local scares=("TRACE DETECTED - REROUTING" "COUNTER-DAEMON LAUNCHED - EVADING" "NEURAL PROBE - BLOCKING"
                    "ALARM TRIPPED - SPOOFING RESPONSE" "BLACKWALL RESONANCE - DAMPENING")
                warning_flash "$(pick "${scares[@]}")"
                spinner "$(pick "Emergency reroute through proxy chain" "Deploying countermeasures" "Scrambling source address" "Injecting false telemetry")" 2
            fi

            sleep "$(awk "BEGIN{printf \"%.3f\", $time_ms / 1000.0 / $steps}")"
        done
        printf "\r  ${BG}  [██████████████████████████████] CRACKED${RST}         \n"
        sleep 0.1
    done

    echo
    printf "  ${BOLD}${BG}  ▶▶ ALL ICE LAYERS BREACHED ◀◀${RST}\n"
    sleep 0.5
}

scene_vault_loot() {
    local vaults=("Arasaka Secure Vault" "Militech R&D Archive" "NetWatch Evidence Locker" "Biotechnica Gene Library" "Zetatech AI Repository")
    local vault=$(pick "${vaults[@]}")

    echo
    hr "═" "${DIM}${BY}"
    printf "${BOLD}${BY}  ◈ VAULT CONTENTS: ${vault}${RST}\n\n"
    sleep 0.3

    type_out "  Listing secrets..." "$C" 0.02; echo
    sleep 0.3

    local paths=("secret/soulkiller/v3.1-source" "secret/project-reliquary/schematics"
        "pki/root-ca/master-key" "secret/ncpd/officer-payroll" "secret/exec/offshore-accounts"
        "secret/biolab/implant-defects-suppressed" "auth/militech-backdoor-persistent"
        "secret/blackwall/fragment-alpha" "secret/engram/construct-$(randhex 4)"
        "secret/orbital/targeting-data" "secret/ai-research/turing-pass-prototype"
        "secret/political/mayor-blackmail" "creds/nusa-mil-sat/launch-auth"
        "secret/braindance/illegal-xbd-studio-network" "secret/relic/biochip-v2-firmware"
        "secret/netrunner/bartmoss-legacy-tools" "secret/cyberpsycho/trigger-frequencies")

    local descs=("Source code for neural copying technology" "Orbital weapons platform schematics"
        "Root certificate authority - signs ALL corporate certs" "Compromised law enforcement personnel list"
        "Board member offshore accounts (Cayman, Swiss, Lunar)" "Suppressed cyberware defect data (2.3M affected)"
        "Persistent access key to rival corporate network" "Self-modifying AI fragment from beyond the Blackwall"
        "Digitized human consciousness - identity unknown" "Pre-loaded targeting coordinates for 6 major cities"
        "AI that passed Turing test - contained but aware" "Kompromat on Night City mayor"
        "Military satellite launch authentication codes" "Illegal braindance production studio locations"
        "Relic biochip firmware - consciousness transfer protocol" "Lost netrunner tools from the DataKrash era"
        "Frequencies that trigger cyberpsychosis in implant users")

    local num=$((RANDOM % 5 + 4))
    local used_idx=()
    for ((v = 0; v < num; v++)); do
        local idx
        while true; do
            idx=$((RANDOM % ${#paths[@]}))
            local dup=0
            for u in "${used_idx[@]}"; do [[ "$u" == "$idx" ]] && dup=1 && break; done
            ((dup == 0)) && break
        done
        used_idx+=("$idx")

        local sizes=("4.2 KB" "1.1 MB" "24.7 MB" "189.3 MB" "856 KB" "45.2 MB" "12 KB" "2.1 GB" "340 MB" "78.5 MB")
        local sz="${sizes[$((RANDOM % ${#sizes[@]}))]}"
        local icon=$(pick "◆" "◇" "●")
        local tc=$(pick "$BY" "$BR" "$BM")

        printf "  ${BOLD}${tc}${icon}${RST} ${W}%-48s${RST} ${DIM}[%s]${RST}\n" "${paths[$idx]}" "$sz"
        printf "    ${DIM}${tc}${descs[$idx]}${RST}\n"
        sleep 0.2
    done

    echo
    local reactions=("...this is enough to start a war." "...they'll kill to get this back."
        "...the world needs to see this." "...this changes everything."
        "...we're sitting on a nuclear bomb of data." "...V would want this."
        "...Rogue is going to lose her mind when she sees this.")
    printf "  ${BOLD}${W}  $(pick "${reactions[@]}")${RST}\n\n"
    sleep 0.5

    printf "  ${BOLD}${BM}  Beginning vault exfiltration...${RST}\n\n"
    for idx in "${used_idx[@]}"; do
        progress "Downloading ${paths[$idx]##*/}" "$(pick "$BY" "$BC" "$BM")" "$(awk "BEGIN{printf \"%.1f\", 0.5 + ($RANDOM % 15) / 10.0}")"
    done

    echo
    spinner "AES-256-GCM encryption + steganographic packaging" 2
    printf "  ${BG}✓${RST} ${W}Vault contents secured across distributed dead drops.${RST}\n"
    sleep 0.5
}

scene_shell_exploit() {
    local targets=("Jenkins CI 2.434" "GitLab CE 16.7" "Confluence 8.5" "Grafana 10.2" "Apache Tomcat 10.1" "Kibana 8.11" "Webmin 2.100" "SonarQube 10.3")
    local target=$(pick "${targets[@]}")
    local host="$(randip)"
    local port=$(pick 8080 8443 3000 9090 8888 7990)
    local user=$(pick "jenkins" "gitlab-runner" "www-data" "tomcat" "grafana" "nobody" "confluence")

    echo
    hr "═" "${DIM}${M}"
    printf "${BOLD}${BY}  ◈ EXPLOITING: ${target}${RST}\n\n"

    type_out "  Connecting to ${host}:${port}..." "$C" 0.02; echo
    sleep 0.4

    local vulns=("Script Console is ENABLED" "RCE via OGNL injection" "Path traversal in file upload"
        "Deserialization flaw (CVE-2077-$(randhex 4))" "Default admin credentials (!)" "SSRF to internal metadata"
        "Template injection in user field" "JWT secret is 'changeme'")
    printf "  ${BG}✓${RST} ${target} - ${BOLD}${BY}$(pick "${vulns[@]}")${RST}\n"
    sleep 0.3

    local payloads=("Groovy reverse shell" "Python staged payload" "Bash /dev/tcp callback" "OGNL code execution" "Serialized Java gadget chain")
    type_out "  Injecting payload: $(pick "${payloads[@]}")..." "$C" 0.02; echo
    sleep 0.3

    local hostname=$(pick "corp-ci-01" "git-prod-03" "wiki-internal" "mon-grafana-02" "app-server-07" "dev-build-12")
    spinner "Waiting for callback on port $((RANDOM % 9000 + 1024))" 2
    printf "  ${BOLD}${BG}  ▶ SHELL RECEIVED${RST} ${DIM}as${RST} ${BY}${user}${RST}${DIM}@${hostname}${RST}\n\n"
    sleep 0.3

    # Interactive shell simulation
    local cmds=(
        "whoami|${user}"
        "id|uid=$(($RANDOM % 1000 + 100))(${user}) gid=$(($RANDOM % 1000 + 100))(${user}) groups=$(($RANDOM % 1000 + 100))(${user}),27(sudo)"
        "uname -a|Linux ${hostname} 6.1.0-rpi7-rpi-v8 #1 SMP PREEMPT Debian 6.1.63-1 aarch64 GNU/Linux"
        "cat /etc/hostname|${hostname}"
    )
    for cmd_pair in "${cmds[@]}"; do
        IFS='|' read -r cmd output <<< "$cmd_pair"
        printf "  ${DIM}${C}${user}@${hostname}:~\$${RST} ${W}%s${RST}\n" "$cmd"
        sleep 0.2
        printf "  %s\n" "$output"
        sleep 0.15
    done

    printf "  ${DIM}${C}${user}@${hostname}:~\$${RST} ${W}find / -name '*.conf' -o -name '*.properties' -readable 2>/dev/null${RST}\n"
    sleep 0.5

    local files=("/opt/deploy/db-credentials.properties" "/etc/vault/token" "/var/lib/${user}/.ssh/id_rsa"
        "/opt/config/ldap-bind.conf" "/home/svc-account/.env" "/etc/kubernetes/admin.conf")
    local picked_files=()
    for ((f = 0; f < 3 + RANDOM % 3; f++)); do
        local pf="${files[$((RANDOM % ${#files[@]}))]}"
        picked_files+=("$pf")
        if ((RANDOM % 2 == 0)); then
            printf "  ${BOLD}${BY}%s${RST}\n" "$pf"
        else
            printf "  ${DIM}%s${RST}\n" "$pf"
        fi
        sleep 0.1
    done

    sleep 0.3
    local best="${picked_files[0]}"
    printf "\n  ${DIM}${C}${user}@${hostname}:~\$${RST} ${W}cat %s${RST}\n\n" "$best"
    sleep 0.4

    printf "${DIM}${R}  ┌─ %s ──────────────────────────────┐${RST}\n" "$(basename "$best")"
    local keys=("db.host" "db.pass" "vault.token" "ldap.bind_pw" "api.secret" "ssh.passphrase" "k8s.token")
    local vals=("$(randip)" "Zer0C00l_$(randhex 4)!@#" "hvs.CAESI$(randhex 20)" "Corp_Ldap_$(randhex 6)"
        "sk-$(randhex 24)" "arasaka$(randhex 8)" "eyJhbG$(randhex 16)")
    for ((k = 0; k < 3 + RANDOM % 3; k++)); do
        printf "  ${DIM}│${RST} ${C}%-14s${RST} = ${BOLD}${BR}%s${RST}\n" \
            "${keys[$((k % ${#keys[@]}))]}" "${vals[$((k % ${#vals[@]}))]}"
        sleep 0.1
    done
    printf "${DIM}${R}  └──────────────────────────────────────────────────┘${RST}\n\n"

    printf "  ${BOLD}${BM}  Credentials harvested. Pivoting deeper.${RST}\n"
    sleep 0.5
}

scene_intercept() {
    echo
    hr "═" "${DIM}${BY}"
    printf "${BOLD}${BY}  ◈ INTERCEPTED TRANSMISSION${RST}\n\n"
    sleep 0.3

    local senders=("rogue@fixers.nc" "v@afterlife.nc" "judy@mox.gang" "panam@aldecaldos.nomad"
        "t-bug@darknet.onion" "spider.murphy@ghost.net" "alt@cyberspace.null" "kerry@rockerboy.nc"
        "river@ncpd-internal.gov" "mitch@aldecaldos.nomad" "evelyn@dolls.nc" "takemura@burner.onion")
    local recips=("unknown@darknet.onion" "deadrop-7@secure.mesh" "handler@fixers.nc" "broadcast@pirate.radio"
        "all@resist.nc" "voodoo-boys@pacifica.nc")

    local from=$(pick "${senders[@]}")
    local to=$(pick "${recips[@]}")

    printf "  ${DIM}FROM: ${BC}%s${RST}\n" "$from"
    printf "  ${DIM}TO:   ${BC}%s${RST}\n" "$to"
    printf "  ${DIM}ENCR: ${BY}AES-256-GCM + ChaCha20 layered${RST}\n"
    printf "  ${DIM}SIZE: %d bytes${RST}\n\n" $((RANDOM % 4000 + 200))

    printf "  ${DIM}Decrypting"
    for ((d = 0; d < 12; d++)); do printf "."; sleep 0.15; done
    printf "${RST}\n\n"

    local messages=(
        "The SoulKiller data is confirmed authentic. Arasaka's been copying engrams of\n  political leaders without consent. We have proof of at least 14 subjects.\n  Release this to the media and it's over for them."
        "Militech knows about the breach. They're mobilizing a counter-netrunner team.\n  You have maybe 12 hours before they trace the dead drops.\n  Move everything to the Aldecaldos backup cache NOW."
        "V - the biochip is degrading faster than Hellman predicted. The construct is\n  bleeding into your neural patterns. You need the Arasaka prototype to survive.\n  Meet me at the No-Tell Motel. Come alone."
        "Voodoo Boys tried to use me as a proxy to breach the Blackwall again.\n  They don't understand what's on the other side. I do. I've been there.\n  Whatever you downloaded from that vault - do NOT execute it."
        "Found the corpo rat. It's someone in our crew. They've been feeding\n  location data to Arasaka for six months. I won't say the name on comms.\n  Tomorrow, Afterlife, back booth. Watch your mirrors getting there."
        "The implant recall data is worse than we thought. It's not just degradation -\n  the cyberware is phoning home. Every implant is a tracking device.\n  2.3 million people in Night City alone. They know where everyone is."
        "I cracked the orbital platform control codes. Reliquary isn't a defense system.\n  It's a first-strike weapon. Pre-loaded targets include Night City, Moscow,\n  Shanghai, São Paulo, Lagos, and Berlin. This is extinction-level."
        "NetWatch offered me a deal. Full immunity, new identity, out of Night City.\n  All I have to do is give them your handle and the relay coordinates.\n  Told them to flatline themselves. But they'll find someone who won't."
    )

    local msg=$(pick "${messages[@]}")
    printf "  ${BY}"
    while IFS= read -r line; do
        type_out "$line" "$BY" 0.012
        echo
    done <<< "$(echo -e "$msg")"
    printf "${RST}\n"

    sleep 0.5
    local reactions=("Saving to encrypted archive." "Forwarding to all dead drops." "This needs to go public."
        "Acknowledged. Adjusting operational parameters." "Well, shit.")
    printf "  ${DIM}${C}  > %s${RST}\n" "$(pick "${reactions[@]}")"
    sleep 0.5
}

scene_trace_evasion() {
    echo
    hr "═" "${BOLD}${BR}"
    printf "${BOLD}${BR}  ◈ COUNTER-INTRUSION ALERT${RST}\n\n"

    warning_flash "ACTIVE TRACE DETECTED ON PRIMARY TUNNEL"
    echo

    local attackers=("Arasaka SOC Team" "NetWatch Division 9" "Militech Cyber Command" "Kang-Tao Red Cell" "Unknown APT Group")
    local atk=$(pick "${attackers[@]}")
    local atk_ip="$(randip)"

    printf "  ${BOLD}${BR}  ATTACKER: ${BY}%s${RST}\n" "$atk"
    printf "  ${BOLD}${BR}  ORIGIN:   ${W}%s${RST}\n" "$atk_ip"
    printf "  ${BOLD}${BR}  METHOD:   ${W}%s${RST}\n\n" "$(pick "Reverse trace via compromised hop" "Timing correlation attack" "Traffic analysis on exit node" "Daemon implant in relay 3" "SIGINT triangulation")"
    sleep 0.5

    printf "  ${BM}Initiating evasion protocol...${RST}\n\n"

    local steps=("Killing primary tunnel" "Activating backup relay chain" "Rotating all encryption keys"
        "Spoofing false endpoint at $(randip)" "Injecting chaff traffic on $(pick 3 5 7 12) decoy routes"
        "Deploying counter-daemon to attacker node" "Re-establishing connection via new route")

    for step in "${steps[@]}"; do
        spinner "$step" "$((1 + RANDOM % 2))"
    done

    echo
    printf "  ${BOLD}${BG}  TRACE EVADED${RST}\n"
    printf "  ${DIM}${C}  Attacker has been fed false coordinates pointing to a Militech subnet.${RST}\n"
    printf "  ${DIM}${C}  New tunnel stable. Continuing operations.${RST}\n"
    sleep 0.5
}

scene_decrypt_file() {
    echo
    hr "═" "${DIM}${BC}"
    printf "${BOLD}${BC}  ◈ DECRYPTION THREAD${RST}\n\n"

    local fname="$(randhex 8).enc"
    local fsize="$((RANDOM % 500 + 10)) $(pick "KB" "MB")"
    printf "  ${DIM}File: ${W}%s${RST} ${DIM}(%s)${RST}\n" "$fname" "$fsize"
    printf "  ${DIM}Encryption: ${W}%s${RST}\n\n" "$(pick "AES-256-CBC" "ChaCha20-Poly1305" "Twofish-256" "Serpent-256-GCM" "Triple-layered XSalsa20")"

    progress "Cracking encryption key" "$M" "$(awk "BEGIN{printf \"%.1f\", 1.5 + ($RANDOM % 20) / 10.0}")"
    progress "Decrypting payload" "$C" 1.0
    echo

    printf "  ${BG}✓${RST} ${W}Decryption successful.${RST}\n\n"
    sleep 0.3

    local reveals=(
        "Contents: Board meeting recording. CEO authorizes 'acceptable casualties'\n    in Night City water supply contamination. 340,000 people affected."
        "Contents: Satellite imagery of Militech black site in Nevada desert.\n    Underground facility, est. 200+ personnel. Unknown purpose."
        "Contents: Email chain proving Arasaka board rigged Night City mayoral election.\n    Three previous mayors were corpo puppets."
        "Contents: Research data - prototype AI achieved self-awareness 6 months ago.\n    Containment status: QUESTIONABLE. Last diagnostic showed escape attempts."
        "Contents: Financial records showing Trauma Team denies service to specific\n    zip codes. 12,000+ preventable deaths in Watson district alone."
        "Contents: Blueprints for neural implant kill switch. Can remotely disable\n    any Arasaka-manufactured cyberware. Affects est. 8 million units worldwide."
        "Contents: Personnel file - deep cover agent inside NCPD Internal Affairs.\n    Has been suppressing corpo crime investigations for 7 years."
        "Contents: Video archive - illegal braindance recordings from Clouds.\n    Victims include 3 city council members. Classic blackmail operation."
        "Contents: Technical readout - the Blackwall is degrading. NetWatch estimates\n    total failure in 18-36 months. They're keeping it classified."
    )

    local reveal=$(pick "${reveals[@]}")
    printf "  ${BY}"
    while IFS= read -r line; do
        type_out "$line" "$BY" 0.015
        echo
    done <<< "$(echo -e "$reveal")"
    printf "${RST}\n"
    sleep 0.5
}

scene_memory_forensics() {
    echo
    hr "═" "${DIM}${M}"
    printf "${BOLD}${BM}  ◈ MEMORY FORENSICS${RST}\n\n"

    local target_host=$(pick "core-router-01" "vault-primary" "exec-workstation-CEO" "soc-analyst-04" "dc-01.arasaka.corp")
    type_out "  Analyzing RAM dump from: ${target_host}" "$C" 0.02; echo
    type_out "  Dump size: $((RANDOM % 32 + 8)) GB" "$DIM$C" 0.015; echo
    echo
    sleep 0.3

    printf "  ${DIM}${M}── Extracting memory segments ──${RST}\n\n"
    hexdump_block $((RANDOM % 6 + 6))
    echo

    progress "Carving process memory" "$M" 1.5
    progress "Extracting strings" "$C" 1.0
    progress "Rebuilding heap objects" "$M" 1.2
    echo

    printf "  ${BOLD}${BY}  Interesting artifacts found:${RST}\n\n"

    local artifacts=(
        "Cleartext password in browser process: ${BR}Yorinobu_Sama_2077!${RST}"
        "SSH private key (RSA-4096) in ssh-agent memory"
        "Vault token with root policy: ${BR}hvs.$(randhex 24)${RST}"
        "Cached Kerberos TGT for ${BY}ARASAKA\\\\domain-admin${RST}"
        "Browser session cookie for ${BY}internal.arasaka.corp/soulkiller-dashboard${RST}"
        "Decrypted email draft: 'Authorize termination of asset SILVERHAND'"
        "Slack webhook URL with admin permissions"
        "AWS root account credentials in environment variables"
    )

    local num_artifacts=$((RANDOM % 3 + 3))
    for ((a = 0; a < num_artifacts; a++)); do
        printf "  ${BG}●${RST} ${DIM}%s${RST}\n" "${artifacts[$((RANDOM % ${#artifacts[@]}))]}"
        sleep 0.2
    done
    echo

    printf "  ${BOLD}${BM}  Memory forensics complete. %d credentials extracted.${RST}\n" "$num_artifacts"
    sleep 0.5
}

scene_lateral_movement() {
    echo
    hr "═" "${DIM}${C}"
    printf "${BOLD}${BC}  ◈ LATERAL MOVEMENT${RST}\n\n"

    type_out "  Mapping internal network topology..." "$C" 0.02; echo
    sleep 0.4

    local subnets=("172.16.1.0/24 (DMZ)" "172.16.2.0/24 (Corporate)" "172.16.5.0/24 (Dev/Test)" 
        "172.16.10.0/24 (Executive)" "172.16.50.0/24 (R&D)" "172.16.99.0/24 (Secure)")
    local method_opts=("Pass-the-Hash" "SSH key reuse" "Kerberoasting" "LDAP credential spray" "Token impersonation" "SMB relay" "WMI execution")

    printf "\n${DIM}${C}"
    cat << 'TOPO'
      YOU ──► [DMZ] ──► [CORP] ──► [DEV/TEST]
                │                      │
                ▼                      ▼
             [EXEC] ◄──────────── [R&D LAB]
                │
                ▼
            [SECURE]  ◄── HIGH VALUE TARGET
TOPO
    printf "${RST}\n"
    sleep 0.8

    local hops=$((RANDOM % 4 + 3))
    for ((h = 0; h < hops; h++)); do
        local subnet="${subnets[$((h % ${#subnets[@]}))]}"
        local method=$(pick "${method_opts[@]}")
        local host=$(pick "ws-$(randhex 4)" "srv-$(randhex 4)" "dc-0$((RANDOM%3+1))" "app-$(randhex 3)" "db-$(randhex 3)")

        printf "  ${BC}▸ HOP $((h+1))${RST} → ${W}%s${RST} via ${BY}%s${RST}\n" "$subnet" "$method"
        spinner "Authenticating to ${host}" "$((1 + RANDOM % 2))"
        printf "  ${BG}✓${RST} ${DIM}Shell on ${BY}%s${RST} ${DIM}(%s)${RST}\n\n" "$host" "$(pick "SYSTEM" "root" "Administrator" "domain-admin")"
        sleep 0.2
    done

    printf "  ${BOLD}${BG}  Lateral movement complete. %d hops, %d hosts owned.${RST}\n" "$hops" "$hops"
    sleep 0.5
}

# ══════════════════════════════════════════
#  BOOT SEQUENCE (plays once)
# ══════════════════════════════════════════

printf "\n"
hr "─" "${DIM}${C}"

glitch "  ██████╗ ██╗   ██╗██████╗ ██╗   ██╗███████╗" "$BM" 4
glitch "  ██╔══██╗╚██╗ ██╔╝██╔══██╗██║   ██║██╔════╝" "$BM" 3
glitch "  ██████╔╝ ╚████╔╝ ██████╔╝██║   ██║███████╗" "$BC" 3
glitch "  ██╔══██╗  ╚██╔╝  ██╔══██╗██║   ██║╚════██║" "$BC" 3
glitch "  ██████╔╝   ██║   ██║  ██║╚██████╔╝███████║" "$BM" 4
glitch "  ╚═════╝    ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚══════╝" "$BM" 3

hr "─" "${DIM}${C}"

sleep 0.2
type_out "  BYRUS SYSTEMS v4.7.2 // UNAUTHORIZED ACCESS TERMINAL" "$DIM$C" 0.01; echo
type_out "  NODE: NCX-$(randhex 4)-$(randhex 4)-$(randhex 4)" "$DIM$M" 0.015; echo
type_out "  $(date '+%Y-%m-%d %H:%M:%S') UTC // NIGHT CITY METROPOLITAN AREA" "$DIM$Y" 0.01; echo
echo

sleep 0.3
printf "${BOLD}${BM}  ◈ SYSTEM BOOTSTRAP${RST}\n\n"

progress "Loading neural firmware" "$M" 0.6
progress "Mounting ghost partition /dev/shm0" "$C" 0.5
progress "Injecting daemon: kr4k3n.dll" "$M" 0.4
progress "Spoofing MAC/HWID identifiers" "$C" 0.5
progress "Establishing quantum mesh relay" "$M" 0.7

echo
spinner "Negotiating encrypted tunnel" 2
spinner "Verifying zero-knowledge auth" 2

echo
printf "  ${BG}◈${RST} Bootstrap complete. Jacking in.\n"
sleep 0.5

# ══════════════════════════════════════════
#  MAIN LOOP: ambient → scene → repeat
# ══════════════════════════════════════════

all_scenes=(scene_portscan scene_database_raid scene_ice_breach scene_vault_loot
    scene_shell_exploit scene_intercept scene_trace_evasion scene_decrypt_file
    scene_memory_forensics scene_lateral_movement)

last_scene=-1

while true; do
    # Brief ambient (30-60 seconds of chatter)
    ambient $((RANDOM % 8 + 6)) 1.5

    # Pick a scene we didn't just do
    while true; do
        pick_idx=$((RANDOM % ${#all_scenes[@]}))
        ((pick_idx != last_scene)) && break
    done
    last_scene=$pick_idx

    # Run it
    ${all_scenes[$pick_idx]}
done
