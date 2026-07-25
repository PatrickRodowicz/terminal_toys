#!/bin/bash
# CYBERPUNK FIXER NETWORK TERMINAL v1
# Underground street-level terminal experience
# Run: bash cyberpunk2.sh

cleanup() { tput cnorm; tput sgr0; clear; exit 0; }
trap cleanup INT TERM

# Colors — warmer neon palette
R='\e[31m'; G='\e[32m'; Y='\e[33m'; B='\e[34m'; M='\e[35m'; C='\e[36m'
BR='\e[91m'; BG='\e[92m'; BY='\e[93m'; BB='\e[94m'; BM='\e[95m'; BC='\e[96m'
W='\e[97m'; DIM='\e[2m'; BOLD='\e[1m'; RST='\e[0m'
BLINK='\e[5m'

clear; tput civis
cols=$(tput cols)

# ── Utilities ──

hr() {
    local ch="${1:-─}" color="${2:-${DIM}${BY}}"
    printf "${color}"
    for ((i = 0; i < cols; i++)); do printf "%s" "$ch"; done
    printf "${RST}\n"
}

flicker() {
    local text="$1" color="$2" iters="${3:-3}"
    for ((g = 0; g < iters; g++)); do
        printf "\r${DIM}${color}%s${RST}" "$text"
        sleep 0.06
        printf "\r${BOLD}${color}%s${RST}" "$text"
        sleep 0.04
    done
    printf "\r${color}%s${RST}\n" "$text"
}

type_out() {
    local text="$1" color="${2:-$BY}" speed="${3:-0.02}"
    printf "${color}"
    for ((i = 0; i < ${#text}; i++)); do
        printf "%s" "${text:$i:1}"
        sleep "$speed"
    done
    printf "${RST}"
}

progress() {
    local label="$1" color="$2" width=30 time="${3:-1.0}"
    local steps=20
    local sleep_t
    sleep_t=$(awk "BEGIN{printf \"%.3f\", $time / $steps}")
    for ((i = 0; i <= steps; i++)); do
        local filled=$((i * width / steps))
        local pct=$((i * 100 / steps))
        printf "\r${color}  %-28s ${RST}${color}[" "$label"
        for ((j = 0; j < width; j++)); do
            if ((j <= filled)); then printf "▰"; else printf "${DIM}▱${RST}${color}"; fi
        done
        printf "] ${W}%3d%%${RST}" "$pct"
        sleep "$sleep_t"
    done
    printf "\r${color}  %-28s ${RST}${color}[" "$label"
    for ((j = 0; j < width; j++)); do printf "▰"; done
    printf "] ${BG}OK${RST}      \n"
}

spinner() {
    local msg="$1" duration="$2" color="${3:-${DIM}${BY}}"
    local frames=('◜' '◝' '◞' '◟')
    local end=$((SECONDS + duration))
    while ((SECONDS < end)); do
        for f in "${frames[@]}"; do
            printf "\r  ${BM}%s${RST} ${color}%s${RST}" "$f" "$msg"
            sleep 0.1
        done
    done
    printf "\r  ${BG}◉${RST} ${color}%s${RST}\n" "$msg"
}

alert_pulse() {
    local msg="$1"
    for ((i = 0; i < 3; i++)); do
        printf "\r  ${BOLD}${BR}▐ %s ▌${RST}" "$msg"
        sleep 0.12
        printf "\r  ${DIM}${R}▐ %s ▌${RST}" "$msg"
        sleep 0.12
    done
    printf "\r  ${BOLD}${BR}▐ %s ▌${RST}" "$msg"
    sleep 0.08
    printf "\r  ${DIM}${R}▐ %s ▌${RST}\n" "$msg"
}

randhex() { for ((i = 0; i < ${1:-8}; i++)); do printf '%x' $((RANDOM % 16)); done; }
randip() { echo "$((RANDOM%254+1)).$((RANDOM%255)).$((RANDOM%255)).$((RANDOM%254+1))"; }
randcred() { printf '%d' $((RANDOM % 90000 + 10000)); }
pick() { local arr=("$@"); echo "${arr[$((RANDOM % ${#arr[@]}))]}"; }

randprice() {
    local min="$1" max="$2"
    local range=$((max - min))
    local val=$((RANDOM % range + min))
    printf '%s' "$val"
}

format_eddies() {
    printf '%d' "$1" | sed ':a;s/\B[0-9]\{3\}\>/,&/;ta'
}

# ── Ambient chatter (street-level) ──

ambient() {
    local lines="${1:-8}" delay="${2:-1.2}"
    for ((n = 0; n < lines; n++)); do
        case $((RANDOM % 8)) in
            0) printf "  ${DIM}${BY}[%s]${RST} ${DIM}NCPD Scanner: %s in %s // %s${RST}\n" \
                "$(date +%H:%M:%S)" \
                "$(pick "10-31 in progress" "shots fired" "traffic stop" "cyberpsycho sighting" "vehicle pursuit" "welfare check")" \
                "$(pick "Watson" "Westbrook" "Heywood" "Pacifica" "Santo Domingo" "City Center" "Japantown" "Kabuki" "Arroyo" "Rancho Coronado")" \
                "$(pick "2 units responding" "MAXTAC requested" "Trauma Team en route" "suspect fled on foot" "code 4 all clear")" ;;
            1) printf "  ${DIM}${BM}◈${RST} ${DIM}Eddie transfer: %s₲ → wallet %s${RST}\n" \
                "$(format_eddies $((RANDOM % 50000 + 500)))" "$(randhex 12)" ;;
            2) printf "  ${DIM}${G}▪${RST} ${DIM}%s${RST}\n" \
                "$(pick "Dead drop confirmed @ coords $(randhex 4):$(randhex 4)" \
                       "Asset in position, awaiting greenlight" \
                       "Ripperdoc on standby, clinic 3" \
                       "Transport clean, plates swapped" \
                       "Package delivered to locker $(randhex 3)" \
                       "Burner phone rotated" \
                       "Safe house sweep: clear")" ;;
            3) printf "  ${DIM}${BR}!${RST} ${DIM}Gang alert: %s activity near %s${RST}\n" \
                "$(pick "Maelstrom" "Tyger Claws" "Valentinos" "6th Street" "Animals" "Voodoo Boys" "Scavengers" "Wraiths")" \
                "$(pick "Kabuki market" "Jig-Jig Street" "the pier" "Megabuilding H8" "Cherry Blossom" "Totentanz" "El Coyote" "Lizzie's Bar")" ;;
            4) printf "  ${DIM}${C}[%s]${RST} ${DIM}Fixnet relay: %d msgs queued | %d clients | lat %dms${RST}\n" \
                "$(date +%H:%M:%S)" $((RANDOM % 40 + 2)) $((RANDOM % 200 + 30)) $((RANDOM % 150 + 10)) ;;
            5) printf "  ${DIM}${M}♦${RST} ${DIM}Bounty update: %s — %s₲ — %s${RST}\n" \
                "$(pick "Target spotted in Pacifica" "Confirmation pending" "Contract extended 48h" "Payout increased" "Target relocated")" \
                "$(format_eddies $((RANDOM % 80000 + 5000)))" \
                "$(pick "ACTIVE" "PENDING" "HOT" "EXPIRING")" ;;
            6) printf "  ${DIM}${BY}⊕${RST} ${DIM}Crypto: %s %s %s%%${RST}\n" \
                "$(pick "NC-COIN" "DGTL-YEN" "EURO-D" "CORPO-X" "NUKE-BIT" "GHOST-₲")" \
                "$(pick "▲" "▼")" \
                "$((RANDOM % 15 + 1)).$((RANDOM % 99))" ;;
            7) printf "  ${DIM}${R}▪${RST} ${DIM}Surveillance: camera %s-%03d feed %s${RST}\n" \
                "$(pick "WAT" "WBK" "HWD" "PAC" "SDO" "CTR")" \
                $((RANDOM % 999)) \
                "$(pick "nominal" "looped" "offline" "tampered" "flagged")" ;;
        esac
        sleep "$(awk "BEGIN{printf \"%.1f\", $delay * (0.5 + ($RANDOM % 10) / 10.0)}")"
    done
}

# ══════════════════════════════════════════
#  SCENES
# ══════════════════════════════════════════

scene_black_market() {
    echo
    hr "▬" "${DIM}${BY}"
    printf "${BOLD}${BY}  ♦ BLACK MARKET AUCTION — ${BLINK}${BR}LIVE${RST}\n\n"

    local house=$(pick "Afterlife Exchange" "Pacifica Underground" "Kabuki Night Market" "Watson Grey Bazaar" "Heywood Backroom")
    type_out "  House: ${house}" "$DIM$M" 0.02; echo
    type_out "  Bidders connected: $((RANDOM % 40 + 12)) (encrypted)" "$DIM$C" 0.015; echo
    echo
    sleep 0.3

    local items=(
        "Militech M-76e Omaha (untraceable)|Weapon|$(randprice 3000 8000)"
        "Kiroshi Mk.4 Optics (mil-spec)|Cyberware|$(randprice 15000 45000)"
        "Gorilla Arms v3 (overclocked)|Cyberware|$(randprice 20000 60000)"
        "Netrunner Deck — Raven Microcyb Mk.5|Tech|$(randprice 30000 80000)"
        "Sandevistan Mk.3 (black market mod)|Cyberware|$(randprice 40000 120000)"
        "Soulkiller Fragment (partial)|Data|$(randprice 200000 500000)"
        "NCPD Patrol Route Database (current month)|Intel|$(randprice 10000 35000)"
        "Arasaka Executive Biometrics (cloned)|Access|$(randprice 50000 150000)"
        "Quadra Type-66 Avenger (stolen, clean VIN)|Vehicle|$(randprice 70000 180000)"
        "Trauma Team Platinum Card (hijacked)|Service|$(randprice 100000 300000)"
        "Mantis Blades (prototype, ceramic)|Cyberware|$(randprice 25000 70000)"
        "Braindance Wreath (unregistered)|Tech|$(randprice 5000 20000)"
        "Delamain Cab Override Module|Tech|$(randprice 8000 25000)"
        "Blackwall Daemon Sample (contained)|Data|$(randprice 500000 999000)"
    )

    local num_lots=$((RANDOM % 4 + 4))
    local used=()
    for ((lot = 0; lot < num_lots; lot++)); do
        local idx
        while true; do
            idx=$((RANDOM % ${#items[@]}))
            local dup=0
            for u in "${used[@]}"; do [[ "$u" == "$idx" ]] && dup=1 && break; done
            ((dup == 0)) && break
        done
        used+=("$idx")

        IFS='|' read -r item_name item_cat item_price <<< "${items[$idx]}"

        local cat_color="$DIM"
        case "$item_cat" in
            Cyberware) cat_color="$BC" ;;
            Weapon) cat_color="$BR" ;;
            Data|Intel) cat_color="$BY" ;;
            Tech) cat_color="$BM" ;;
            Vehicle) cat_color="$BG" ;;
            Access|Service) cat_color="$BB" ;;
        esac

        printf "  ${DIM}${BY}╔══${RST} ${BOLD}${BY}LOT #%03d${RST} ${DIM}${BY}"  "$((lot + 1))"
        for ((p = 0; p < 44; p++)); do printf "═"; done
        printf "╗${RST}\n"
        printf "  ${DIM}${BY}║${RST}  ${BOLD}${W}%s${RST}\n" "$item_name"
        printf "  ${DIM}${BY}║${RST}  ${cat_color}[%s]${RST}  ${DIM}Ask: ${BY}%s₲${RST}" "$item_cat" "$(format_eddies $item_price)"
        if ((item_price >= 100000)); then
            printf "  ${BOLD}${BR}${BLINK}▸ HIGH VALUE${RST}"
        fi
        printf "\n"
        printf "  ${DIM}${BY}╚"
        for ((p = 0; p < 57; p++)); do printf "═"; done
        printf "╝${RST}\n"

        # Bidding war
        local current_bid=$item_price
        local num_bids=$((RANDOM % 5 + 2))
        local bidders=("GHOST-$(randhex 3)" "ANON-$(randhex 3)" "NOM4D-$(randhex 2)" "FXER-$(randhex 3)"
            "REDQN-$(randhex 2)" "BLK-$(randhex 3)" "V00D0-$(randhex 2)" "CHRM-$(randhex 3)")

        local winner=""
        for ((b = 0; b < num_bids; b++)); do
            local bump=$((current_bid / (RANDOM % 8 + 4)))
            current_bid=$((current_bid + bump))
            winner="${bidders[$((RANDOM % ${#bidders[@]}))]}"
            printf "    ${DIM}${BY}▸${RST} ${DIM}%s${RST} bids ${BOLD}${BY}%s₲${RST}" "$winner" "$(format_eddies $current_bid)"
            if ((b > 0 && RANDOM % 3 == 0)); then
                printf "  ${BR}⚡ outbid!${RST}"
            fi
            printf "\n"
            sleep 0.25
        done

        sleep 0.3
        printf "    ${DIM}${BY}⌛ Going once...${RST}"; sleep 0.5
        printf " ${BY}going twice...${RST}"; sleep 0.7
        echo
        flicker "    ★ SOLD to ${winner} for $(format_eddies $current_bid)₲" "$BG" 3
        echo
    done

    local total_vol=$((RANDOM % 2000000 + 500000))
    printf "  ${DIM}Session volume: ${BY}%s₲${RST} ${DIM}// House takes 8%%${RST}\n" "$(format_eddies $total_vol)"
    sleep 0.5
}

scene_bounty_board() {
    echo
    hr "▬" "${DIM}${BR}"
    printf "${BOLD}${BR}  ♦ BOUNTY BOARD — NIGHT CITY FIXERS NETWORK${RST}\n\n"
    sleep 0.3

    local targets=(
        "Kozlov, A.|Ex-Militech operative gone rogue|$(randprice 20000 80000)|ALIVE ONLY"
        "[HANDLE: Scorpion]|Maelstrom lieutenant, organ trade|$(randprice 50000 120000)|DEAD OR ALIVE"
        "Dr. Faye Lau|Ripperdoc selling client data to corpos|$(randprice 15000 40000)|ALIVE PREFERRED"
        "NCPD Det. Morrison|Dirty cop, Tyger Claw payroll|$(randprice 30000 90000)|EVIDENCE REQUIRED"
        "[UNKNOWN]|Cyberpsycho, last seen Pacifica|$(randprice 60000 150000)|NEUTRALIZE"
        "Tanaka, R.|Arasaka defector with stolen IP|$(randprice 100000 300000)|ALIVE ONLY — FRAGILE"
        "Cassidy 'Bonesaw'|Animals enforcer, 3 counts murder|$(randprice 40000 100000)|DEAD OR ALIVE"
        "[HANDLE: Pixel]|Rogue netrunner, data ransom ops|$(randprice 70000 200000)|ALIVE — DECK INTACT"
        "Maria Alvarez|Valentino boss, turf expansion|$(randprice 25000 75000)|INTIMIDATION ONLY"
        "Unit 4-17|Stolen Militech combat drone|$(randprice 80000 250000)|RECOVER INTACT"
    )

    local dangers=("LOW" "MODERATE" "HIGH" "EXTREME" "SUICIDE")
    local danger_colors=("$BG" "$BY" "$BY" "$BR" "$BOLD$BR")
    local fixers=("Rogue" "Padre" "Wakako" "Dino" "Regina" "Dakota" "Mr. Hands" "El Capitan" "Muamar")

    local num=$((RANDOM % 4 + 4))
    local used=()
    for ((c = 0; c < num; c++)); do
        local idx
        while true; do
            idx=$((RANDOM % ${#targets[@]}))
            local dup=0
            for u in "${used[@]}"; do [[ "$u" == "$idx" ]] && dup=1 && break; done
            ((dup == 0)) && break
        done
        used+=("$idx")

        IFS='|' read -r tgt_name tgt_desc tgt_price tgt_cond <<< "${targets[$idx]}"
        local didx=$((RANDOM % ${#dangers[@]}))
        local danger="${dangers[$didx]}"
        local dcol="${danger_colors[$didx]}"
        local fixer=$(pick "${fixers[@]}")

        printf "  ${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n"
        printf "  ${BOLD}${W}  TARGET:${RST}  ${BOLD}${BY}%s${RST}" "$tgt_name"
        if ((RANDOM % 3 == 0)); then
            printf "  ${BOLD}${BLINK}${BG}NEW${RST}"
        fi
        printf "\n"
        printf "  ${DIM}  INTEL:${RST}   ${DIM}%s${RST}\n" "$tgt_desc"
        printf "  ${DIM}  FIXER:${RST}   ${BM}%s${RST}\n" "$fixer"
        printf "  ${DIM}  PAYOUT:${RST}  ${BOLD}${BG}%s₲${RST}\n" "$(format_eddies "$tgt_price")"
        printf "  ${DIM}  TERMS:${RST}   ${W}%s${RST}\n" "$tgt_cond"
        printf "  ${DIM}  DANGER:${RST}  ${dcol}■ %s${RST}\n" "$danger"
        sleep 0.35

        # Rare live update: target eliminated mid-display
        if ((c > 1 && RANDOM % 7 == 0)); then
            sleep 0.4
            local elim_tgt="${tgt_name}"
            for ((flash = 0; flash < 4; flash++)); do
                printf "\r  ${BOLD}${BR}  ▓▓▓ BREAKING: %s — TARGET ELIMINATED ▓▓▓${RST}" "$elim_tgt"
                sleep 0.1
                printf "\r  ${DIM}${R}  ░░░ BREAKING: %s — TARGET ELIMINATED ░░░${RST}" "$elim_tgt"
                sleep 0.1
            done
            printf "\r  ${DIM}${R}  ░░░ CONTRACT CLOSED — %s — payout released ░░░${RST}\n" "$elim_tgt"
            sleep 0.5
        fi
    done

    printf "  ${DIM}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RST}\n\n"
    printf "  ${DIM}%d active contracts // %d mercs online // accept via encrypted handshake${RST}\n" \
        "$((num + RANDOM % 20 + 5))" "$((RANDOM % 80 + 20))"
    sleep 0.5
}

scene_cyberware_diag() {
    echo
    hr "▬" "${DIM}${BC}"
    printf "${BOLD}${BC}  ♦ CYBERWARE DIAGNOSTICS — REMOTE SCAN${RST}\n\n"

    local subjects=("V (Merc — Night City)" "Jackie Welles" "Asset: SCORPION" "Client #$(randhex 4)" "Field Operative $(randhex 3)")
    local subject=$(pick "${subjects[@]}")
    type_out "  Subject: ${subject}" "$W" 0.02; echo
    type_out "  Scanning implant bus..." "$DIM$C" 0.015; echo
    echo
    sleep 0.4

    progress "Neural link handshake" "$BC" 0.6
    progress "Implant enumeration" "$M" 0.8
    progress "Integrity check" "$BC" 0.5
    echo

    local implants=(
        "Kiroshi Optics Mk.3|Optical|NOMINAL|98"
        "Militech Paraline|Neural|NOMINAL|95"
        "Dynalar Sandevistan Mk.2|Nervous System|WARNING|72"
        "Arasaka Quickhack Coprocessor|Frontal Cortex|NOMINAL|91"
        "Gorilla Arms v2|Arms|NOMINAL|88"
        "Reinforced Tendons|Legs|NOMINAL|94"
        "Biomonitor Mk.4|Cardiovascular|NOMINAL|99"
        "Subdermal Armor v3|Integumentary|DEGRADED|61"
        "Mantis Blades (ceramic)|Arms|NOMINAL|85"
        "Kerenzikov Mk.2|Nervous System|WARNING|68"
        "Syn-Lungs|Cardiovascular|NOMINAL|96"
        "Raven Microcyb Mk.4|Operating System|CRITICAL|34"
        "Monowire (heated)|Arms|NOMINAL|90"
        "Threat Detector|Frontal Cortex|NOMINAL|87"
    )

    local num=$((RANDOM % 4 + 5))
    printf "  ${BOLD}${W}  IMPLANT                         SLOT              STATUS     INTEG${RST}\n"
    printf "  ${DIM}──────────────────────────────────────────────────────────────────────${RST}\n"

    local warnings=0
    local criticals=0
    for ((i = 0; i < num; i++)); do
        local idx=$((RANDOM % ${#implants[@]}))
        IFS='|' read -r imp_name imp_slot imp_status imp_integ <<< "${implants[$idx]}"

        local scol="$BG"
        local icol="$BG"
        case "$imp_status" in
            WARNING) scol="$BY"; icol="$BY"; warnings=$((warnings + 1)) ;;
            DEGRADED) scol="$BR"; icol="$BR"; warnings=$((warnings + 1)) ;;
            CRITICAL) scol="$BOLD$BLINK$BR"; icol="$BOLD$BR"; criticals=$((criticals + 1)) ;;
        esac

        if ((imp_integ < 50)); then icol="$BOLD$BR"; fi

        # Animate integrity percentage counting up like a real scan
        local scan_steps=5
        for ((si = 0; si < scan_steps; si++)); do
            local fake_pct=$((RANDOM % imp_integ))
            printf "\r  ${W}  %-32s${RST} ${DIM}%-17s${RST} ${DIM}${C}scanning...${RST} ${DIM}%3d%%${RST}" \
                "$imp_name" "$imp_slot" "$fake_pct"
            sleep 0.04
        done
        printf "\r  ${W}  %-32s${RST} ${DIM}%-17s${RST} ${scol}%-10s${RST} ${icol}%3d%%${RST}\n" \
            "$imp_name" "$imp_slot" "$imp_status" "$imp_integ"
        sleep 0.08
    done

    printf "  ${DIM}──────────────────────────────────────────────────────────────────────${RST}\n\n"

    if ((criticals > 0)); then
        alert_pulse "CRITICAL: ${criticals} implant(s) require immediate ripperdoc attention"
        echo
    fi
    if ((warnings > 0)); then
        printf "  ${BY}!${RST} ${DIM}%d implant(s) showing degradation — schedule maintenance${RST}\n" "$warnings"
    fi

    # Vitals
    printf "\n  ${BOLD}${W}  VITALS${RST}\n"
    printf "  ${DIM}──────────────────────────────────────${RST}\n"
    printf "  ${DIM}  Heart rate:${RST}    ${BG}%d bpm${RST}\n" "$((RANDOM % 30 + 65))"
    printf "  ${DIM}  Blood pressure:${RST} ${BG}%d/%d${RST}\n" "$((RANDOM % 20 + 110))" "$((RANDOM % 15 + 70))"
    printf "  ${DIM}  Neural load:${RST}   ${BY}%d%%${RST}\n" "$((RANDOM % 40 + 45))"
    printf "  ${DIM}  Cyberpsych index:${RST} ${scol}%d.%d / 10.0${RST}\n" "$((RANDOM % 4 + 2))" "$((RANDOM % 10))"
    printf "  ${DIM}  Humanity:${RST}      ${W}%d%%${RST}\n" "$((RANDOM % 30 + 55))"
    sleep 0.5
}

scene_fixer_comms() {
    echo
    hr "▬" "${DIM}${BM}"
    printf "${BOLD}${BM}  ♦ ENCRYPTED FIXER CHANNEL — LIVE${RST}\n\n"
    sleep 0.3

    local channels=("AFTERLIFE-VIP" "FIXNET-PRIME" "DARKPOOL-7" "NOMAD-RELAY" "HEYWOOD-OPS" "PACIFICA-MESH")
    local channel=$(pick "${channels[@]}")
    printf "  ${DIM}Channel: ${BM}%s${RST} ${DIM}// E2E encrypted // %d participants${RST}\n\n" \
        "$channel" "$((RANDOM % 15 + 4))"

    local handles=("Rogue" "Padre" "Wakako" "Dino" "Dakota" "Regina" "Mr.Hands" "V"
        "Nix" "8ug8ear" "Bartmoss_Jr" "Panam" "Saul" "Mitch" "River" "Judy"
        "T0xic" "Zer0Cool" "Sp1der" "GH0ST" "N3tRuNn3r")
    local handle_colors=("$BY" "$BM" "$BC" "$BR" "$BG" "$BB" "$W")

    local conversations=(
        "Need a team for a Maelstrom warehouse hit. Three operators, one netrunner. Payout is 120k, split even.|How hot is the site?|Moderate. Rotating guards, basic cameras. The real problem is the attack dog — a refurbished Minotaur drone.|I'm in. I'll bring EMP charges for the drone.|Good. Meet at El Coyote, midnight. Bring your own iron."
        "Got a client who needs someone extracted from Clouds. Discreetly.|Willing or unwilling extraction?|Willing. They can't leave on their own — contract lock. Need someone to spoof the biometric check.|I know a ripper who can clone the biosig. 15k for his cut.|Done. Send me his contact on a burner. Job window is 48 hours."
        "Arasaka convoy moving through Heywood tomorrow 0600. Lightly armored. Three vehicles.|What's the cargo?|Prototype neural implants. Street value is seven figures easy.|That's a corpo war waiting to happen.|Only if they find out who did it. I have a buyer in Pacifica already lined up."
        "Lost contact with my runner mid-job. Last ping was inside the Biotechnica subnet.|How long ago?|Forty minutes. Either they hit black ICE or got physically jacked out.|I can send a rescue team but it'll cost. 50k retainer.|Do it. That runner has data in their head worth ten times that."
        "Tyger Claws are moving product through Jig-Jig Street again. New route.|So? Let them.|My client owns three blocks on that route. Wants them redirected.|Redirected or stopped?|Redirected. We're not starting a war. Just making the path... inconvenient.|I know someone in 6th Street who'd love to make that intersection messy. Plausible deniability."
        "NCPD is running a sting on Watson rippers tomorrow night.|Which clinics?|All of them. They're doing a sweep — someone in city hall needs headlines.|Spread the word. Every ripper goes dark for 48 hours.|Already moving. Backup clinic in the Badlands is prepped."
    )

    local convo="${conversations[$((RANDOM % ${#conversations[@]}))]}"
    IFS='|' read -ra lines <<< "$convo"

    local participants=()
    for ((p = 0; p < 4; p++)); do
        participants+=("${handles[$((RANDOM % ${#handles[@]}))]}")
    done

    local speaker=0
    for line in "${lines[@]}"; do
        local h="${participants[$((speaker % ${#participants[@]}))]}"
        local hcol="${handle_colors[$((RANDOM % ${#handle_colors[@]}))]}"
        local prefix
        prefix=$(printf "  ${DIM}%s${RST} ${BOLD}${hcol}%-12s${RST} " "$(date +%H:%M:%S)" "$h")

        # Decryption scramble effect — garbled hex resolves into the real message
        local scramble_len=${#line}
        ((scramble_len > 60)) && scramble_len=60
        for ((dec = 0; dec < 3; dec++)); do
            printf "\r%s${DIM}${C}" "$prefix"
            for ((sc = 0; sc < scramble_len; sc++)); do printf '%x' $((RANDOM % 16)); done
            printf "${RST}"
            sleep 0.06
        done
        printf "\r%s" "$prefix"
        # Clear the garbled line before typing the real text
        printf "%*s" "$((scramble_len + 2))" ""
        printf "\r%s" "$prefix"

        type_out "$line" "$DIM" 0.008
        echo
        sleep 0.4
        speaker=$((speaker + 1))
    done

    echo
    printf "  ${DIM}// end of cached buffer // live traffic continues on encrypted relay${RST}\n"
    sleep 0.5
}

scene_gang_intel() {
    echo
    hr "▬" "${DIM}${BR}"
    printf "${BOLD}${BR}  ♦ GANG TERRITORY INTELLIGENCE REPORT${RST}\n\n"

    local gangs=("Maelstrom" "Tyger Claws" "Valentinos" "6th Street" "Animals" "Voodoo Boys" "Scavengers" "Mox")
    local turfs=("Watson" "Westbrook" "Heywood" "Pacifica" "Santo Domingo" "Northside" "Kabuki" "Japantown" "Arroyo" "Rancho Coronado" "Charter Hill" "Vista del Rey")
    local activities=("Recruiting" "Fortifying" "Expanding" "Skirmishing" "Retreating" "Consolidating" "Raiding" "Negotiating")

    printf "  ${DIM}Source: Street-level informant network // Updated %s${RST}\n\n" "$(date +%H:%M)"

    printf "  ${BOLD}${W}  GANG              TURF             ACTIVITY       STRENGTH  THREAT${RST}\n"
    printf "  ${DIM}────────────────────────────────────────────────────────────────────────${RST}\n"

    local num=$((RANDOM % 4 + 5))
    for ((i = 0; i < num; i++)); do
        local gang="${gangs[$((RANDOM % ${#gangs[@]}))]}"
        local turf="${turfs[$((RANDOM % ${#turfs[@]}))]}"
        local act="${activities[$((RANDOM % ${#activities[@]}))]}"
        local strength=$((RANDOM % 500 + 50))
        local threat=$((RANDOM % 10 + 1))

        local tcol="$BG"
        ((threat > 4)) && tcol="$BY"
        ((threat > 7)) && tcol="$BR"

        local acol="$DIM"
        [[ "$act" == "Expanding" || "$act" == "Raiding" ]] && acol="$BY"
        [[ "$act" == "Skirmishing" ]] && acol="$BR"
        [[ "$act" == "Retreating" ]] && acol="$DIM$R"

        printf "  ${BY}  %-17s${RST} ${DIM}%-16s${RST} ${acol}%-14s${RST} ${DIM}~%-8d${RST} ${tcol}%d/10${RST}\n" \
            "$gang" "$turf" "$act" "$strength" "$threat"
        sleep 0.15
    done

    printf "  ${DIM}────────────────────────────────────────────────────────────────────────${RST}\n\n"

    # Rare BREAKING interrupt that flickers over the display
    if ((RANDOM % 3 == 0)); then
        local break_gangs=("Maelstrom" "Tyger Claws" "Valentinos" "6th Street" "Animals" "Voodoo Boys")
        local break_locs=("Watson" "Kabuki" "Japantown" "Heywood" "Pacifica" "Arroyo")
        local break_events=("turf war erupted" "ambush in progress" "convoy hit" "safe house raided" "shootout reported" "territory seized")
        local bg="${break_gangs[$((RANDOM % ${#break_gangs[@]}))]}"
        local bl="${break_locs[$((RANDOM % ${#break_locs[@]}))]}"
        local be="${break_events[$((RANDOM % ${#break_events[@]}))]}"
        local break_msg="${bg} — ${be} in ${bl}"
        for ((bf = 0; bf < 5; bf++)); do
            printf "\r  ${BOLD}${BR}${BLINK}  ▓▓▓ BREAKING ▓▓▓${RST} ${BOLD}${W}%s${RST}" "$break_msg"
            sleep 0.12
            printf "\r  ${DIM}${R}  ░░░ BREAKING ░░░${RST} ${DIM}%s${RST}" "$break_msg"
            sleep 0.1
        done
        printf "\r  ${BY}  ◈ BREAKING:${RST} ${W}%s${RST}%*s\n\n" "$break_msg" 10 ""
        sleep 0.5
    fi

    # Recent incidents
    printf "  ${BOLD}${W}  RECENT INCIDENTS${RST}\n\n"

    local incidents=(
        "Maelstrom / Tyger Claws shootout near Kabuki Market — 7 dead, 3 civilian"
        "Valentinos torched a 6th Street stash house in Arroyo — retaliation expected"
        "Animals spotted testing experimental combat stims in underground ring"
        "Voodoo Boys went dark 72 hours ago — unusual, possibly planning something big"
        "Scavenger organ farm raided by NCPD — survivors say there's a bigger one"
        "Mox expanded protection zone — Tyger Claws probing the new perimeter"
        "Unknown group hijacked Militech supply truck in Santo Domingo"
        "Wraith raiding party hit a Nomad convoy on the eastern highway"
    )

    local num_inc=$((RANDOM % 3 + 2))
    for ((i = 0; i < num_inc; i++)); do
        local inc="${incidents[$((RANDOM % ${#incidents[@]}))]}"
        local age="$((RANDOM % 24 + 1))h ago"
        printf "  ${BR}  ▸${RST} ${DIM}[%s]${RST} %s\n" "$age" "$inc"
        sleep 0.2
    done

    echo
    printf "  ${DIM}  Analysis: Tension index ${BY}HIGH${RST} ${DIM}// Expect escalation within 72h${RST}\n"
    sleep 0.5
}

scene_ripperdoc() {
    echo
    hr "▬" "${DIM}${BG}"
    printf "${BOLD}${BG}  ♦ RIPPERDOC BLACK MARKET INVENTORY${RST}\n\n"

    local clinics=("Vik's Backroom (Watson)" "Cassius Ryder (Northside)" "Fingers M.D. (Jig-Jig)" "Doc Chromatic (Arroyo)"
        "Badlands Mobile Clinic" "Pacifica Underground Chop Shop" "Kabuki Basement Ripper")
    local clinic=$(pick "${clinics[@]}")

    type_out "  Clinic: ${clinic}" "$DIM$M" 0.02; echo
    type_out "  Stock updated: $(date +%H:%M)" "$DIM$C" 0.015; echo
    echo
    sleep 0.3

    printf "  ${BOLD}${W}  ITEM                             GRADE   PRICE         STOCK  RISK${RST}\n"
    printf "  ${DIM}──────────────────────────────────────────────────────────────────────────${RST}\n"

    local cyberware=(
        "Kiroshi Optics Mk.4|Legendary|45,000₲|2|Low"
        "Gorilla Arms v3|Epic|32,000₲|1|Low"
        "Mantis Blades (thermal)|Epic|38,000₲|1|Moderate"
        "Sandevistan Mk.3 (QianT)|Legendary|85,000₲|1|High"
        "Kerenzikov Mk.3|Rare|18,000₲|4|Low"
        "Subdermal Armor Mk.4|Epic|22,000₲|3|Low"
        "Monowire (chemical)|Epic|28,000₲|2|Moderate"
        "Syn-Lungs (mil-spec)|Rare|12,000₲|5|Low"
        "Raven Microcyb Mk.5|Legendary|95,000₲|1|High"
        "Biomonitor Mk.5|Rare|15,000₲|3|Low"
        "Reinforced Tendons v2|Rare|20,000₲|4|Low"
        "Pain Editor|Epic|50,000₲|1|EXTREME"
        "Threat Detector Mk.3|Rare|16,000₲|2|Low"
        "Second Heart|Legendary|120,000₲|1|High"
        "Militech Berserk Mk.4|Legendary|78,000₲|1|High"
        "Heal-on-Kill (blood pump)|Epic|35,000₲|2|Moderate"
    )

    local num=$((RANDOM % 5 + 6))
    local used=()
    for ((i = 0; i < num; i++)); do
        local idx
        while true; do
            idx=$((RANDOM % ${#cyberware[@]}))
            local dup=0
            for u in "${used[@]}"; do [[ "$u" == "$idx" ]] && dup=1 && break; done
            ((dup == 0)) && break
        done
        used+=("$idx")

        IFS='|' read -r cw_name cw_grade cw_price cw_stock cw_risk <<< "${cyberware[$idx]}"

        local gcol="$DIM"
        case "$cw_grade" in
            Legendary) gcol="$BOLD$BY" ;;
            Epic) gcol="$BM" ;;
            Rare) gcol="$BC" ;;
        esac

        local rcol="$BG"
        [[ "$cw_risk" == "Moderate" ]] && rcol="$BY"
        [[ "$cw_risk" == "High" ]] && rcol="$BR"
        [[ "$cw_risk" == "EXTREME" ]] && rcol="$BOLD$BR"

        printf "  ${W}  %-33s${RST} ${gcol}%-9s${RST} ${BG}%-13s${RST} ${DIM}%-6s${RST} ${rcol}%s${RST}\n" \
            "$cw_name" "$cw_grade" "$cw_price" "$cw_stock" "$cw_risk"
        sleep 0.12
    done

    printf "  ${DIM}──────────────────────────────────────────────────────────────────────────${RST}\n\n"

    local warnings=("No warranties. No refunds. No questions."
        "Installation at your own risk. Anesthesia extra."
        "Stolen goods. If Militech comes knocking, you never heard of us."
        "Disclaimer: Side effects may include cyberpsychosis."
        "Cash only. Eddie transfers accepted from clean wallets.")
    printf "  ${DIM}${R}  %s${RST}\n" "$(pick "${warnings[@]}")"
    sleep 0.5
}

scene_vehicle_tracker() {
    echo
    hr "▬" "${DIM}${BB}"
    printf "${BOLD}${BB}  ♦ VEHICLE TRACKING NETWORK${RST}\n\n"

    local ops=("Asset recovery" "Surveillance" "Convoy intercept" "Escape route mapping")
    type_out "  Operation: $(pick "${ops[@]}")" "$DIM$C" 0.02; echo
    echo
    sleep 0.3

    local vehicles=(
        "Quadra Type-66 Avenger|Sport|$(randip)|Westbrook"
        "Villefort Columbus|Sedan|$(randip)|Watson"
        "Chevillon Thrax 388|Truck|$(randip)|Santo Domingo"
        "Mizutani Shion MZ2|Sport|$(randip)|Japantown"
        "Archer Hella EC-D|Economy|$(randip)|Kabuki"
        "Militech Basilisk|APC|$(randip)|Badlands"
        "Delamain Cab #$(randhex 2)|Autonomous|$(randip)|City Center"
        "Yaiba Kusanagi CT-3X|Motorcycle|$(randip)|Heywood"
        "Thorton Galena GA-3|Economy|$(randip)|Arroyo"
        "Rayfield Aerondight|Luxury|$(randip)|North Oak"
    )

    local statuses=("MOVING" "PARKED" "PURSUIT" "LOST SIGNAL" "IDLING")
    local status_colors=("$BG" "$DIM" "$BOLD$BR" "$DIM$R" "$BY")

    local num=$((RANDOM % 4 + 5))
    for ((i = 0; i < num; i++)); do
        local idx=$((RANDOM % ${#vehicles[@]}))
        IFS='|' read -r v_name v_type v_tracker v_loc <<< "${vehicles[$idx]}"
        local sidx=$((RANDOM % ${#statuses[@]}))
        local status="${statuses[$sidx]}"
        local scol="${status_colors[$sidx]}"
        local speed=$((RANDOM % 180))
        [[ "$status" == "PARKED" || "$status" == "LOST SIGNAL" ]] && speed=0

        printf "  ${DIM}├─${RST} ${BOLD}${W}%s${RST} ${DIM}[%s]${RST}\n" "$v_name" "$v_type"
        printf "  ${DIM}│  Location: ${BY}%-18s${RST} ${DIM}Speed: ${W}%3d km/h${RST}  ${DIM}Status: ${scol}%s${RST}\n" \
            "$v_loc" "$speed" "$status"
        printf "  ${DIM}│  Tracker: %s${RST}\n" "$v_tracker"

        if [[ "$status" == "PURSUIT" ]]; then
            printf "  ${DIM}│  ${BR}▸ NCPD units in pursuit — %d stars${RST}\n" "$((RANDOM % 4 + 1))"
        fi
        printf "  ${DIM}│${RST}\n"
        sleep 0.2
    done

    printf "  ${DIM}└─ %d vehicles tracked // GPS refresh: 3s // Feed delay: ~%dms${RST}\n" \
        "$num" "$((RANDOM % 500 + 100))"
    sleep 0.5
}

scene_eddie_laundering() {
    echo
    hr "▬" "${DIM}${BG}"
    printf "${BOLD}${BG}  ♦ EDDIE FLOW — DARK WALLET MONITOR${RST}\n\n"

    local wallets=("wallet-$(randhex 8)" "wallet-$(randhex 8)" "wallet-$(randhex 8)"
        "wallet-$(randhex 8)" "wallet-$(randhex 8)" "wallet-$(randhex 8)")
    local fronts=("El Coyote Cojo LLC" "Night City Laundry Co" "Tom's Diner Holdings"
        "Kabuki Noodle Corp" "Pacifica Real Estate" "Watson Auto Repair"
        "Clouds Entertainment" "Afterlife Bar & Grill" "Lizzie's Media Inc")

    type_out "  Monitoring dark wallet cluster..." "$DIM$C" 0.015; echo
    echo
    sleep 0.3

    local total_moved=0
    local num_txns=$((RANDOM % 6 + 5))
    for ((t = 0; t < num_txns; t++)); do
        local from="${wallets[$((RANDOM % ${#wallets[@]}))]}"
        local to="${wallets[$((RANDOM % ${#wallets[@]}))]}"
        local amount=$((RANDOM % 500000 + 5000))
        total_moved=$((total_moved + amount))

        local tcol="$DIM"
        ((amount > 100000)) && tcol="$BY"
        ((amount > 300000)) && tcol="$BOLD$BY"

        printf "  ${DIM}%s${RST}  ${DIM}%s${RST} → ${DIM}%s${RST}  ${tcol}%s₲${RST}" \
            "$(date +%H:%M:%S)" "${from:0:16}…" "${to:0:16}…" "$(format_eddies $amount)"

        if ((RANDOM % 3 == 0)); then
            local front="${fronts[$((RANDOM % ${#fronts[@]}))]}"
            printf "  ${DIM}via ${M}%s${RST}" "$front"
        fi
        printf "\n"
        sleep 0.3
    done

    echo
    printf "  ${DIM}─────────────────────────────────────────────────────${RST}\n"
    printf "  ${DIM}  Total volume:${RST} ${BOLD}${BG}%s₲${RST}\n" "$(format_eddies $total_moved)"
    printf "  ${DIM}  Laundering layers:${RST} ${W}%d hops avg${RST}\n" "$((RANDOM % 5 + 3))"
    printf "  ${DIM}  Front companies:${RST} ${W}%d active${RST}\n" "$((RANDOM % 8 + 3))"

    local clean_pct=$((RANDOM % 15 + 80))
    printf "  ${DIM}  Clean rating:${RST} ${BG}%d%%${RST} ${DIM}(undetectable by NCPD financial crimes)${RST}\n" "$clean_pct"
    sleep 0.5
}

scene_braindance_analysis() {
    echo
    hr "▬" "${DIM}${M}"
    printf "${BOLD}${BM}  ♦ BRAINDANCE ANALYSIS — EVIDENCE REVIEW${RST}\n\n"

    local sources=("Crime scene recording" "Corpo whistleblower BD" "Street cam composite" "Interrogation session"
        "Trauma Team helmet cam" "Undercover operative" "Stolen Arasaka security BD")
    local source=$(pick "${sources[@]}")
    local duration="$((RANDOM % 30 + 2)):$((RANDOM % 60 | 10#0))$(printf '%02d' $((RANDOM % 60)))"
    local bd_id="BD-$(randhex 6)"

    type_out "  Source: ${source}" "$DIM$M" 0.02; echo
    printf "  ${DIM}ID: %s // Duration: %s // Layers: Visual + Audio + Thermal${RST}\n\n" "$bd_id" "$duration"
    sleep 0.3

    progress "Loading neural pattern" "$M" 0.8
    progress "Decoding sensory layers" "$BM" 1.0
    progress "Reconstructing timeline" "$M" 0.7
    echo

    printf "  ${BOLD}${W}  TIMELINE MARKERS${RST}\n"
    printf "  ${DIM}──────────────────────────────────────────────────────────${RST}\n"

    local markers=(
        "00:00:03|Subject enters building — Kabuki district, unmarked door"
        "00:00:15|Elevator descent — estimated 4 floors below ground"
        "00:00:31|Meeting room — 6 individuals, faces partially obscured"
        "00:01:02|Document exchange — datapad with Arasaka watermark visible"
        "00:01:18|Subject's stress indicators spike — threat detected?"
        "00:01:44|Gunshot — origin: behind subject. Recording destabilizes."
        "00:02:01|Subject fleeing — thermal layer shows 3 pursuers"
        "00:02:23|Vehicle escape — license plate partially captured"
        "00:02:45|Signal lost — subject's BD wreath likely damaged or removed"
    )

    local num=$((RANDOM % 4 + 4))
    for ((i = 0; i < num; i++)); do
        local idx=$((i % ${#markers[@]}))
        IFS='|' read -r ts desc <<< "${markers[$idx]}"

        local mcol="$DIM"
        [[ "$desc" == *"spike"* || "$desc" == *"Gunshot"* || "$desc" == *"lost"* ]] && mcol="$BR"
        [[ "$desc" == *"Arasaka"* || "$desc" == *"Document"* ]] && mcol="$BY"

        printf "  ${BC}  %s${RST}  ${mcol}%s${RST}\n" "$ts" "$desc"
        sleep 0.25
    done

    printf "  ${DIM}──────────────────────────────────────────────────────────${RST}\n\n"

    local findings=(
        "Facial recognition partial match: 73%% confidence on Arasaka exec Hayato Kimura"
        "Audio spectrum analysis reveals a second conversation — whispering in Japanese"
        "Thermal layer inconsistency at 00:01:18 — possible cloaked individual present"
        "Datapad content partially reconstructed — references 'Project Lazarus'"
        "Vehicle identified as registered to a Militech shell company"
        "BD was edited before we received it — 11 seconds removed at 00:01:30"
    )

    printf "  ${BOLD}${BY}  KEY FINDINGS${RST}\n\n"
    local num_f=$((RANDOM % 3 + 2))
    for ((f = 0; f < num_f; f++)); do
        printf "  ${BY}  ▸${RST} ${DIM}%s${RST}\n" "${findings[$((RANDOM % ${#findings[@]}))]}"
        sleep 0.2
    done
    echo
    printf "  ${DIM}  BD saved to encrypted evidence locker.${RST}\n"
    sleep 0.5
}

scene_dead_drop() {
    echo
    hr "▬" "${DIM}${G}"
    printf "${BOLD}${BG}  ♦ DEAD DROP NETWORK STATUS${RST}\n\n"

    type_out "  Scanning dead drop nodes..." "$DIM$C" 0.015; echo
    echo
    sleep 0.3

    local locations=("Watson dumpster 7-C" "Kabuki vending machine #403" "Japantown temple garden"
        "Heywood parking garage L3" "Pacifica pier locker 19" "Santo Domingo rail yard"
        "Northside warehouse 12-B" "Westbrook rooftop AC unit" "Badlands mile marker 47"
        "City Center plaza bench" "Arroyo bridge underpass" "Charter Hill mailbox 221")

    local contents=("Credchip (unknown value)" "Datapad (encrypted)" "Burner phone" "Weapon parts"
        "Cyberware component" "Biometric sample" "Physical documents" "Keys + access cards"
        "Chemical sample" "Braindance shard" "Empty (retrieved)" "COMPROMISED")

    local num=$((RANDOM % 5 + 5))
    for ((i = 0; i < num; i++)); do
        local loc="${locations[$((RANDOM % ${#locations[@]}))]}"
        local cont="${contents[$((RANDOM % ${#contents[@]}))]}"
        local age="$((RANDOM % 72 + 1))h"

        local scol="$BG"
        local status="SECURE"
        local roll=$((RANDOM % 10))
        if ((roll == 0)); then
            status="COMPROMISED"
            scol="$BOLD$BR"
            cont="COMPROMISED"
        elif ((roll == 1)); then
            status="RETRIEVED"
            scol="$DIM"
            cont="Empty (retrieved)"
        elif ((roll < 4)); then
            status="STALE"
            scol="$BY"
            age="$((RANDOM % 200 + 72))h"
        fi

        printf "  ${DIM}◦${RST} ${W}%-34s${RST} ${scol}%-12s${RST} ${DIM}%s${RST}\n" "$loc" "$status" "$age"
        if [[ "$status" != "RETRIEVED" ]]; then
            printf "    ${DIM}Contents: ${M}%s${RST}\n" "$cont"
        fi
        sleep 0.15
    done

    echo
    local compromised=$((RANDOM % 2))
    if ((compromised > 0)); then
        alert_pulse "WARNING: ${compromised} drop(s) compromised — rotate immediately"
        echo
    fi
    printf "  ${DIM}  Network health: %d/%d nodes active // Next rotation: %dh${RST}\n" \
        "$((num - compromised))" "$num" "$((RANDOM % 24 + 6))"
    sleep 0.5
}

scene_contract_briefing() {
    echo
    hr "▬" "${DIM}${BY}"
    printf "${BOLD}${BY}  ♦ CONTRACT BRIEFING — EYES ONLY${RST}\n\n"

    local fixers=("Rogue Amendiares" "Padre" "Wakako Okada" "Dino Dinovic" "Regina Jones" "Dakota Smith" "Mr. Hands" "El Capitan")
    local fixer=$(pick "${fixers[@]}")
    printf "  ${DIM}Issuing fixer:${RST} ${BOLD}${BM}%s${RST}\n" "$fixer"
    printf "  ${DIM}Classification:${RST} ${BR}NEED TO KNOW${RST}\n"
    printf "  ${DIM}Contract ID:${RST} ${DIM}CTR-$(randhex 6)${RST}\n\n"
    sleep 0.4

    local ops=(
        "Extraction|A Biotechnica researcher wants out. They have evidence of illegal human trials. Biotechnica security is already suspicious — the window is 36 hours. Researcher is in a corporate apartment in City Center, floor 47. Building security is automated. Expect drones.|Extract researcher alive with all data intact|Biotechnica rapid response, automated building security, potential NCPD involvement|180,000₲ + data bonus"
        "Sabotage|Militech is testing a new combat drone prototype at their Santo Domingo facility. A rival client wants the test to fail — publicly and spectacularly. Access is through the maintenance tunnels. Drone goes live in 72 hours.|Destroy prototype during live demonstration|Militech security forces, facility lockdown protocols, prototype's own weapons systems|250,000₲"
        "Theft|Arasaka has a physical server in their Japantown office containing unencrypted personnel files. Server is air-gapped — no remote access. Has to be a physical grab. The server is the size of a briefcase.|Retrieve server intact, no traces|Arasaka corporate security, biometric locks, on-site netrunner team|300,000₲"
        "Assassination|A fixer in Heywood has been selling client identities to NCPD. Three mercs are already in prison because of them. The community has decided this is a capital offense. Make it look like gang violence.|Eliminate target, stage scene|Target has personal security detail (2 bodyguards), hardened safe house, paranoia|120,000₲"
        "Delivery|A package needs to move from the Badlands to a ship in Night City harbor. Contents classified. The route passes through three gang territories. Previous courier didn't make it.|Deliver package undamaged within 12 hours|Wraith patrols, Maelstrom checkpoints, NCPD highway interdiction|90,000₲ + transport expenses"
        "Investigation|Three netrunners have gone missing in Pacifica over two weeks. All were working independent jobs, no connection. Someone or something is hunting runners. Find out what and make it stop.|Identify threat, neutralize if possible|Unknown — previous investigators also went silent|200,000₲ + hazard pay"
    )

    local op="${ops[$((RANDOM % ${#ops[@]}))]}"
    IFS='|' read -r op_type op_desc op_obj op_threat op_pay <<< "$op"

    printf "  ${BOLD}${W}  OPERATION TYPE:${RST}  ${BY}%s${RST}\n\n" "$op_type"

    printf "  ${DIM}  BRIEFING:${RST}\n"
    # Word-wrap the description
    local words=($op_desc)
    local line="  "
    for word in "${words[@]}"; do
        if ((${#line} + ${#word} + 1 > 70)); then
            printf "${DIM}%s${RST}\n" "$line"
            line="  $word"
        else
            line="$line $word"
        fi
    done
    printf "${DIM}%s${RST}\n\n" "$line"
    sleep 0.3

    printf "  ${BOLD}${W}  OBJECTIVE:${RST}\n"
    printf "  ${BG}  %s${RST}\n\n" "$op_obj"

    printf "  ${BOLD}${W}  EXPECTED OPPOSITION:${RST}\n"
    printf "  ${BR}  %s${RST}\n\n" "$op_threat"

    printf "  ${BOLD}${W}  PAYOUT:${RST}\n"
    printf "  ${BOLD}${BY}  %s${RST}\n\n" "$op_pay"
    sleep 0.3

    local notes=("Fixer wants zero corpo escalation — keep it clean."
        "Client is paying double for speed. Every hour past deadline costs 10k."
        "If this goes sideways, you're on your own. Fixer will deny involvement."
        "Bonus for zero casualties. Client has a conscience apparently."
        "Secondary objective: retrieve any intel of opportunity. Pays extra."
        "Do NOT engage MAXTAC under any circumstances. Abort if they show.")
    printf "  ${DIM}  NOTE: ${BY}%s${RST}\n" "$(pick "${notes[@]}")"
    sleep 0.5
}

# ══════════════════════════════════════════
#  BOOT SEQUENCE
# ══════════════════════════════════════════

printf "\n"
hr "─" "${DIM}${BY}"

flicker "  ███████╗██╗██╗  ██╗███╗   ██╗███████╗████████╗" "$BY" 4
flicker "  ██╔════╝██║╚██╗██╔╝████╗  ██║██╔════╝╚══██╔══╝" "$BY" 3
flicker "  █████╗  ██║ ╚███╔╝ ██╔██╗ ██║█████╗     ██║   " "$BM" 3
flicker "  ██╔══╝  ██║ ██╔██╗ ██║╚██╗██║██╔══╝     ██║   " "$BM" 3
flicker "  ██║     ██║██╔╝ ██╗██║ ╚████║███████╗   ██║   " "$BY" 4
flicker "  ╚═╝     ╚═╝╚═╝  ╚═╝╚═╝  ╚═══╝╚══════╝   ╚═╝   " "$BY" 3

hr "─" "${DIM}${BY}"

sleep 0.2
type_out "  FIXNET UNDERGROUND v2.1.0 // NIGHT CITY FIXER NETWORK" "$DIM$BY" 0.01; echo
type_out "  NODE: NCF-$(randhex 4)-$(randhex 4)-$(randhex 4)" "$DIM$M" 0.015; echo
type_out "  $(date '+%Y-%m-%d %H:%M:%S') UTC // ENCRYPTED MESH RELAY" "$DIM$Y" 0.01; echo
echo

sleep 0.3
printf "${BOLD}${BM}  ♦ NETWORK BOOTSTRAP${RST}\n\n"

progress "Connecting to mesh network" "$BY" 0.6
progress "Verifying fixer credentials" "$M" 0.5
progress "Loading bounty database" "$BY" 0.4
progress "Syncing gang territory maps" "$M" 0.6
progress "Connecting to dark wallet pool" "$BY" 0.5

echo
spinner "Establishing secure fixer channel" 2
spinner "Synchronizing dead drop network" 2

# Random chance of a connection scare during boot
if ((RANDOM % 2 == 0)); then
    echo
    sleep 0.3
    for ((scare = 0; scare < 6; scare++)); do
        printf "\r  ${BOLD}${BR}▓▓▓ CONNECTION INTERCEPTED — TRACING SOURCE ▓▓▓${RST}"
        sleep 0.1
        printf "\r  ${DIM}${R}░░░ CONNECTION INTERCEPTED — TRACING SOURCE ░░░${RST}"
        sleep 0.08
    done
    sleep 0.4
    printf "\r  ${DIM}${C}... analyzing intercept ...${RST}%*s" 30 ""
    sleep 0.6
    printf "\r  ${BG}◉${RST} ${DIM}${G}Decoy triggered — real channel secure.${RST}%*s\n" 20 ""
    sleep 0.4
fi

echo
printf "  ${BG}♦${RST} Fixnet online. Welcome back, choom.\n"
sleep 0.5

# ══════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════

all_scenes=(scene_black_market scene_bounty_board scene_cyberware_diag scene_fixer_comms
    scene_gang_intel scene_ripperdoc scene_vehicle_tracker scene_eddie_laundering
    scene_braindance_analysis scene_dead_drop scene_contract_briefing)

last_scene=-1

while true; do
    ambient $((RANDOM % 8 + 6)) 1.5

    while true; do
        pick_idx=$((RANDOM % ${#all_scenes[@]}))
        ((pick_idx != last_scene)) && break
    done
    last_scene=$pick_idx

    ${all_scenes[$pick_idx]}
done
