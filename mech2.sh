#!/bin/bash
# MECH COMBAT HUD — TACTICAL DISPLAY v1
# Full-screen animated cockpit dashboard
# Run: bash mech2.sh

cleanup() { tput cnorm; tput sgr0; clear; exit 0; }
trap cleanup INT TERM EXIT

# ── Colors ──
HUD='\e[32m'; HUDB='\e[92m'; WARN='\e[93m'; CRIT='\e[91m'
DIM='\e[2m'; BOLD='\e[1m'; RST='\e[0m'; INFO='\e[97m'

clear; tput civis

# ── Terminal dimensions ──
ROWS=$(tput lines)
COLS=$(tput cols)

if ((ROWS < 22 || COLS < 70)); then
    tput cnorm
    echo "Terminal too small. Need at least 70x22 (have ${COLS}x${ROWS})."
    exit 1
fi

# ── Cursor positioning (1-indexed ANSI) ──
goto() { printf '\e[%d;%dH' "$1" "$2"; }

# ── Layout constants ──
LEFT_W=$((COLS / 2 - 1))
RIGHT_X=$((COLS / 2 + 1))
RIGHT_W=$((COLS - RIGHT_X))

GRID_ROWS=11
GRID_COLS=$(( (LEFT_W - 6) / 3 ))
((GRID_COLS > 15)) && GRID_COLS=15
((GRID_COLS % 2 == 0)) && GRID_COLS=$((GRID_COLS - 1))
GRID_CX=$((GRID_COLS / 2))
GRID_CY=$((GRID_ROWS / 2))

TACT_TOP=2
TACT_LEFT=2
TACT_BOTTOM=$((TACT_TOP + GRID_ROWS + 2))

WAVE_TOP=$((TACT_BOTTOM + 1))
WAVE_WIDTH=$((COLS - 6))
((WAVE_WIDTH > 120)) && WAVE_WIDTH=120

COMP_TOP=$((WAVE_TOP + 4))
STAT_TOP=$((COMP_TOP + 2))

# ── Mech identity ──
MECH_NAMES=("Atlas AS7-D" "Marauder MAD-3R" "Warhammer WHM-6R" "Timber Wolf Prime" "King Crab KGC-000" "Centurion CN9-A" "Madcat Mk.II" "Vulture MK-IV")
CALLSIGNS=("IRONCLAD" "WARHOUND" "BASILISK" "TEMPEST" "LONGBOW" "SENTINEL" "REAPER" "VANGUARD")
PILOTS=("Specter" "Havoc" "Viper" "Ghost" "Jackal" "Raptor" "Nomad" "Wolf")
MECH="${MECH_NAMES[$((RANDOM % ${#MECH_NAMES[@]}))]}"
CALLSIGN="${CALLSIGNS[$((RANDOM % ${#CALLSIGNS[@]}))]}"
PILOT="${PILOTS[$((RANDOM % ${#PILOTS[@]}))]}"

# ── Data state ──

# Contacts (parallel arrays)
MAX_CONTACTS=8
NUM_CONTACTS=0
declare -a C_ROW C_COL C_TYPE  # type: 0=hostile 1=friendly 2=unknown
declare -a C_PREV_ROW C_PREV_COL  # previous position for trails

# Terrain flavor
TERRAINS=("URBAN ZONE" "OPEN FIELD" "FOREST" "CANYON" "TUNDRA" "DESERT" "SWAMP" "MOUNTAIN" "COASTAL" "INDUSTRIAL")
TERRAIN="${TERRAINS[$((RANDOM % ${#TERRAINS[@]}))]}"

# Signal interference
INTERFERENCE=0
INTERFERENCE_TTL=0

# Gauges
declare -a G_VAL G_TGT
G_NAME=("REACTOR " "HEAT    " "ARMOR   " "POWER   " "COOLANT " "AMMO    " "GYRO    ")
G_UNIT=("C" "%" "%" "%" "%" "%" "%")
G_MAX=(600 100 100 100 100 100 100)
G_INIT=(340 25 85 95 80 78 100)
NUM_GAUGES=${#G_NAME[@]}
for ((i = 0; i < NUM_GAUGES; i++)); do G_VAL[$i]=${G_INIT[$i]}; G_TGT[$i]=${G_INIT[$i]}; done

# Waveform (circular buffers)
declare -a WAVE HEART
for ((i = 0; i < WAVE_WIDTH; i++)); do WAVE[$i]=3; HEART[$i]=0; done
WAVE_HEAD=0
WAVE_PHASE=0
HEART_PHASE=0
HEART_BEAT=(0 1 3 6 7 6 3 1 0)
HEART_BEAT_LEN=${#HEART_BEAT[@]}

# Sine table (20 entries, values -3 to 3)
SINE=(0 1 2 3 3 3 2 1 0 -1 -2 -3 -3 -3 -2 -1 0 1 2 3)
SINE_LEN=${#SINE[@]}

# Waveform characters
WC=('▁' '▂' '▃' '▄' '▅' '▆' '▇' '█')

# Compass
BEARING=$((RANDOM % 360))
SPEED=$((30 + RANDOM % 60))
BEARING_DRIFT=0

# Sweep angle (0-7 for 8 sectors)
SWEEP=0

# Events
EVENT_MSG=""
EVENT_TTL=0
FLASH_TTL=0  # screen border flash on critical events

# Mission clock
MISSION_START=$SECONDS

# Frame counter
FRAME=0

# Ambient comms chatter
COMMS_CHATTER=(
    "COMMAND: All units hold sector lines"
    "LANCE-2: Contacts moving grid north"
    "COMMAND: Artillery strike inbound, mark waypoint"
    "LANCE-4: Hostile down, sector clear"
    "COMMAND: Resupply ETA twelve minutes"
    "LANCE-2: Thermal spike bearing 270"
    "COMMAND: ROE update — weapons free"
    "LANCE-3: Taking fire, request support"
    "COMMAND: Satellite pass in sixty seconds"
    "LANCE-4: ECM interference, comms degraded"
    "COMMAND: Mission clock reset, new phase"
    "LANCE-2: Visual on hostile lance, four mechs"
    "COMMAND: Priority target redesignated"
    "LANCE-3: Armor critical, falling back"
    "COMMAND: Air support on station"
    "LANCE-2: IFF transponder check, acknowledge"
    "COMMAND: Terrain scan complete, forwarding"
    "LANCE-4: Reactor warning on unit 3"
)

# ── Initialize contacts ──
init_contacts() {
    NUM_CONTACTS=$((RANDOM % 4 + 3))
    for ((i = 0; i < NUM_CONTACTS; i++)); do
        C_ROW[$i]=$((RANDOM % GRID_ROWS))
        C_COL[$i]=$((RANDOM % GRID_COLS))
        while ((C_ROW[$i] == GRID_CY && C_COL[$i] == GRID_CX)); do
            C_ROW[$i]=$((RANDOM % GRID_ROWS))
            C_COL[$i]=$((RANDOM % GRID_COLS))
        done
        C_TYPE[$i]=$((RANDOM % 3))
        C_PREV_ROW[$i]=${C_ROW[$i]}
        C_PREV_COL[$i]=${C_COL[$i]}
    done
}
init_contacts

# ── Update functions ──

update_contacts() {
    for ((i = 0; i < NUM_CONTACTS; i++)); do
        if ((RANDOM % 100 < 12)); then
            local dir=$((RANDOM % 4))
            local nr=${C_ROW[$i]} nc=${C_COL[$i]}
            case $dir in
                0) ((nr > 0)) && nr=$((nr - 1)) ;;
                1) ((nr < GRID_ROWS - 1)) && nr=$((nr + 1)) ;;
                2) ((nc > 0)) && nc=$((nc - 1)) ;;
                3) ((nc < GRID_COLS - 1)) && nc=$((nc + 1)) ;;
            esac
            if ! ((nr == GRID_CY && nc == GRID_CX)); then
                C_PREV_ROW[$i]=${C_ROW[$i]}; C_PREV_COL[$i]=${C_COL[$i]}
                C_ROW[$i]=$nr; C_COL[$i]=$nc
            fi
        fi
    done

    # Occasionally add contacts
    if ((RANDOM % 120 == 0 && NUM_CONTACTS < MAX_CONTACTS)); then
        local idx=$NUM_CONTACTS
        if ((RANDOM % 2 == 0)); then
            C_ROW[$idx]=$(( RANDOM % 2 == 0 ? 0 : GRID_ROWS - 1 ))
            C_COL[$idx]=$((RANDOM % GRID_COLS))
        else
            C_ROW[$idx]=$((RANDOM % GRID_ROWS))
            C_COL[$idx]=$(( RANDOM % 2 == 0 ? 0 : GRID_COLS - 1 ))
        fi
        C_TYPE[$idx]=$((RANDOM % 3))
        C_PREV_ROW[$idx]=${C_ROW[$idx]}
        C_PREV_COL[$idx]=${C_COL[$idx]}
        NUM_CONTACTS=$((NUM_CONTACTS + 1))
        local nt=""
        case ${C_TYPE[$idx]} in
            0) nt="HOSTILE" ;; 1) nt="FRIENDLY" ;; 2) nt="UNIDENT" ;;
        esac
        EVENT_MSG="◉ NEW ${nt} CONTACT — BEARING $(printf '%03d' $((RANDOM % 360)))"
        EVENT_TTL=22; FLASH_TTL=3
    fi

    # Occasionally remove contacts
    if ((RANDOM % 200 == 0 && NUM_CONTACTS > 2)); then
        local kill_idx=$((RANDOM % NUM_CONTACTS))
        # Shift remaining
        for ((j = kill_idx; j < NUM_CONTACTS - 1; j++)); do
            C_ROW[$j]=${C_ROW[$((j+1))]}
            C_COL[$j]=${C_COL[$((j+1))]}
            C_TYPE[$j]=${C_TYPE[$((j+1))]}
            C_PREV_ROW[$j]=${C_PREV_ROW[$((j+1))]}
            C_PREV_COL[$j]=${C_PREV_COL[$((j+1))]}
        done
        NUM_CONTACTS=$((NUM_CONTACTS - 1))
        local kt=""
        case ${C_TYPE[$kill_idx]} in
            0) kt="HOSTILE ELIMINATED" ;; 1) kt="FRIENDLY LOST" ;; 2) kt="CONTACT LOST" ;;
        esac
        EVENT_MSG="✕ ${kt} — SIGNAL DROPPED"
        EVENT_TTL=22
    fi
}

update_gauges() {
    for ((i = 0; i < NUM_GAUGES; i++)); do
        if ((G_VAL[$i] < G_TGT[$i])); then
            G_VAL[$i]=$((G_VAL[$i] + 1))
        elif ((G_VAL[$i] > G_TGT[$i])); then
            G_VAL[$i]=$((G_VAL[$i] - 1))
        fi
        # New target drift
        if ((RANDOM % 80 == 0)); then
            local range=$((G_MAX[$i] / 8))
            G_TGT[$i]=$((G_VAL[$i] + RANDOM % (range * 2 + 1) - range))
            ((G_TGT[$i] < 5)) && G_TGT[$i]=5
            ((G_TGT[$i] > G_MAX[$i])) && G_TGT[$i]=${G_MAX[$i]}
        fi
    done

    # Events
    if ((RANDOM % 120 == 0)); then
        G_TGT[1]=$((G_VAL[1] + 15 + RANDOM % 15))
        ((G_TGT[1] > 95)) && G_TGT[1]=95
        EVENT_MSG="⚠ HEAT SPIKE — REDUCE OUTPUT"; EVENT_TTL=20; FLASH_TTL=4
    fi
    if ((RANDOM % 160 == 0)); then
        G_TGT[2]=$((G_VAL[2] - 5 - RANDOM % 10))
        ((G_TGT[2] < 15)) && G_TGT[2]=15
        EVENT_MSG="◈ IMPACT — ARMOR DAMAGE"; EVENT_TTL=20; FLASH_TTL=8
    fi
    if ((RANDOM % 140 == 0)); then
        G_TGT[5]=$((G_VAL[5] - 3 - RANDOM % 5))
        ((G_TGT[5] < 8)) && G_TGT[5]=8
        EVENT_MSG="▸ WEAPONS FIRED — AMMO EXPENDED"; EVENT_TTL=15
    fi
    # Slow reactor recovery
    if ((RANDOM % 40 == 0 && G_VAL[1] > 40)); then
        G_TGT[1]=$((G_VAL[1] - RANDOM % 5 - 2))
        ((G_TGT[1] < 15)) && G_TGT[1]=15
    fi

    # Gyro instability
    if ((RANDOM % 200 == 0)); then
        G_TGT[6]=$((G_VAL[6] - 8 - RANDOM % 12))
        ((G_TGT[6] < 40)) && G_TGT[6]=40
        EVENT_MSG="⚠ GYRO INSTABILITY — COMPENSATING"; EVENT_TTL=18
    fi

    # Power surge
    if ((RANDOM % 250 == 0 && EVENT_TTL == 0)); then
        G_TGT[3]=$((G_VAL[3] - 10 - RANDOM % 15))
        ((G_TGT[3] < 30)) && G_TGT[3]=30
        G_TGT[0]=$((G_VAL[0] + 30 + RANDOM % 40))
        ((G_TGT[0] > 580)) && G_TGT[0]=580
        EVENT_MSG="⚡ POWER SURGE — REACTOR SPIKE"; EVENT_TTL=22; FLASH_TTL=5
    fi

    # Coolant recovery
    if ((RANDOM % 60 == 0 && G_VAL[4] < 60)); then
        G_TGT[4]=$((G_VAL[4] + RANDOM % 10 + 5))
        ((G_TGT[4] > 95)) && G_TGT[4]=95
    fi

    # Gradual gyro recovery
    if ((RANDOM % 30 == 0 && G_VAL[6] < 90)); then
        G_TGT[6]=$((G_VAL[6] + RANDOM % 4 + 1))
        ((G_TGT[6] > 100)) && G_TGT[6]=100
    fi
}

update_waveform() {
    # Signal interference
    ((INTERFERENCE_TTL > 0)) && INTERFERENCE_TTL=$((INTERFERENCE_TTL - 1))
    ((INTERFERENCE_TTL == 0)) && INTERFERENCE=0
    if ((RANDOM % 300 == 0 && INTERFERENCE == 0)); then
        INTERFERENCE=1; INTERFERENCE_TTL=$((8 + RANDOM % 15))
        if ((EVENT_TTL == 0)); then
            EVENT_MSG="◇ SIGNAL INTERFERENCE DETECTED"
            EVENT_TTL=18
        fi
    fi

    # Signal waveform: sine + noise (or static during interference)
    local val
    if ((INTERFERENCE)); then
        val=$((RANDOM % 8))
    else
        local base=$((4 + SINE[WAVE_PHASE % SINE_LEN]))
        local noise=$((RANDOM % 3 - 1))
        val=$((base + noise))
    fi
    ((val < 0)) && val=0; ((val > 7)) && val=7
    WAVE[$WAVE_HEAD]=$val

    # Heartbeat: mostly flat with periodic beats
    local hval=0
    local beat_pos=$((HEART_PHASE % 20))
    if ((beat_pos < HEART_BEAT_LEN)); then
        hval=${HEART_BEAT[$beat_pos]}
    else
        hval=$((RANDOM % 2))
    fi
    HEART[$WAVE_HEAD]=$hval

    WAVE_HEAD=$(( (WAVE_HEAD + 1) % WAVE_WIDTH ))
    WAVE_PHASE=$((WAVE_PHASE + 1))
    HEART_PHASE=$((HEART_PHASE + 1))
}

update_bearing() {
    # Slow random drift
    if ((RANDOM % 5 == 0)); then
        if ((RANDOM % 20 == 0)); then
            BEARING_DRIFT=$((RANDOM % 5 - 2))
        fi
        BEARING=$((BEARING + BEARING_DRIFT))
        ((BEARING < 0)) && BEARING=$((BEARING + 360))
        ((BEARING >= 360)) && BEARING=$((BEARING - 360))
    fi
    # Speed fluctuation
    if ((RANDOM % 8 == 0)); then
        SPEED=$((SPEED + RANDOM % 3 - 1))
        ((SPEED < 0)) && SPEED=0; ((SPEED > 120)) && SPEED=120
    fi
}

update_sweep() {
    ((FRAME % 4 == 0)) && SWEEP=$(( (SWEEP + 1) % 8 ))
}

update_events() {
    ((EVENT_TTL > 0)) && EVENT_TTL=$((EVENT_TTL - 1))
    ((EVENT_TTL == 0)) && EVENT_MSG=""
    ((FLASH_TTL > 0)) && FLASH_TTL=$((FLASH_TTL - 1))

    # Ambient comms chatter
    if ((RANDOM % 90 == 0 && EVENT_TTL == 0)); then
        EVENT_MSG="${COMMS_CHATTER[$((RANDOM % ${#COMMS_CHATTER[@]}))]}"
        EVENT_TTL=25
    fi

    # Terrain shift
    if ((RANDOM % 500 == 0)); then
        TERRAIN="${TERRAINS[$((RANDOM % ${#TERRAINS[@]}))]}"
        if ((EVENT_TTL == 0)); then
            EVENT_MSG="TERRAIN: ${TERRAIN} — RECALIBRATING SENSORS"
            EVENT_TTL=20
        fi
    fi

    # Proximity alert
    for ((i = 0; i < NUM_CONTACTS; i++)); do
        if ((C_TYPE[i] == 0)); then
            local dy=$((C_ROW[i] - GRID_CY))
            local dx=$((C_COL[i] - GRID_CX))
            if ((dy * dy + dx * dx <= 2 && RANDOM % 60 == 0 && EVENT_TTL == 0)); then
                EVENT_MSG="⚠ PROXIMITY ALERT — HOSTILE AT CLOSE RANGE"
                EVENT_TTL=25; FLASH_TTL=6
            fi
        fi
    done
}

# ── Draw functions ──

draw_title() {
    goto 1 1
    printf '%b' "${DIM}${HUD}"
    for ((i = 0; i < COLS; i++)); do printf '═'; done
    goto 1 3
    # Blinking REC indicator
    if ((FRAME % 12 < 8)); then
        printf '%b' "${RST}${BOLD}${CRIT} ● ${RST}"
    else
        printf '%b' "${RST}   "
    fi
    printf '%b' "${BOLD}${HUDB}${MECH} ${RST}${DIM}${HUD}·${RST}${HUDB} ${CALLSIGN} ${RST}${DIM}${HUD}·${RST}${HUDB} ${PILOT} ${RST}"

    # Mission elapsed time + terrain
    local elapsed=$((SECONDS - MISSION_START))
    local mins=$((elapsed / 60))
    local secs=$((elapsed % 60))
    goto 1 $((COLS - 30))
    printf '%b' "${DIM}${HUD}${TERRAIN} T+$(printf '%02d:%02d' $mins $secs) $(date +%H:%M) ${RST}"
}

draw_tactical() {
    local top=$TACT_TOP left=$TACT_LEFT
    # Width = from left to one col before RIGHT_X (leave gap)
    local width=$((RIGHT_X - left - 1))
    local right_col=$((left + width - 1))

    # Sweep indicator for title
    local sweep_chars=('N' 'NE' 'E' 'SE' 'S' 'SW' 'W' 'NW')
    local sc="${sweep_chars[$SWEEP]}"

    # Top border — fill exact width
    goto $top $left
    printf '%b' "${DIM}${HUD}┌─ TACTICAL ─ ${RST}${HUDB}SCAN:${sc}${RST}${DIM}${HUD} "
    # Fill remaining with ─ up to the ┐
    # Visible prefix: ┌─ TACTICAL ─ SCAN:XX  = 20 + len(sc)
    local header_used=$((20 + ${#sc}))
    for ((i = header_used; i < width - 1; i++)); do printf '─'; done
    printf '%b' "┐${RST}"

    for ((r = 0; r < GRID_ROWS; r++)); do
        goto $((top + 1 + r)) $left
        printf '%b' "${DIM}${HUD}│${RST} "

        for ((c = 0; c < GRID_COLS; c++)); do
            if ((r == GRID_CY && c == GRID_CX)); then
                # Crosshair pulses
                if ((FRAME % 10 < 5)); then
                    printf '%b' "${BOLD}${HUDB}★${RST}  "
                else
                    printf '%b' "${HUDB}✦${RST}  "
                fi
                continue
            fi

            # Determine if cell is in the current sweep sector
            local dy=$((r - GRID_CY))
            local dx=$((c - GRID_CX))
            local in_sweep=0
            # Map dx/dy to octant (0=N, 1=NE, 2=E, etc.)
            if ((dy < 0 && dx >= -1 && dx <= 1)) && ((SWEEP == 0)); then in_sweep=1; fi
            if ((dy < 0 && dx > 0)) && ((SWEEP == 1)); then in_sweep=1; fi
            if ((dy >= -1 && dy <= 1 && dx > 0)) && ((SWEEP == 2)); then in_sweep=1; fi
            if ((dy > 0 && dx > 0)) && ((SWEEP == 3)); then in_sweep=1; fi
            if ((dy > 0 && dx >= -1 && dx <= 1)) && ((SWEEP == 4)); then in_sweep=1; fi
            if ((dy > 0 && dx < 0)) && ((SWEEP == 5)); then in_sweep=1; fi
            if ((dy >= -1 && dy <= 1 && dx < 0)) && ((SWEEP == 6)); then in_sweep=1; fi
            if ((dy < 0 && dx < 0)) && ((SWEEP == 7)); then in_sweep=1; fi

            local found=0
            for ((ci = 0; ci < NUM_CONTACTS; ci++)); do
                if ((C_ROW[ci] == r && C_COL[ci] == c)); then
                    local blink=0
                    ((C_TYPE[ci] == 0 && FRAME % 6 < 3)) && blink=1
                    case ${C_TYPE[ci]} in
                        0) if ((in_sweep)); then printf '%b' "${BOLD}${CRIT}▲${RST}  "
                           elif ((blink)); then printf '%b' "${BOLD}${CRIT}▲${RST}  "
                           else printf '%b' "${CRIT}▲${RST}  "; fi ;;
                        1) if ((in_sweep)); then printf '%b' "${BOLD}${HUDB}◆${RST}  "
                           else printf '%b' "${HUDB}◆${RST}  "; fi ;;
                        2) if ((in_sweep)); then printf '%b' "${BOLD}${WARN}?${RST}  "
                           else printf '%b' "${WARN}?${RST}  "; fi ;;
                    esac
                    found=1; break
                fi
            done

            # Check for contact trails (previous positions)
            if ((found == 0)); then
                for ((ci = 0; ci < NUM_CONTACTS; ci++)); do
                    if ((C_PREV_ROW[ci] == r && C_PREV_COL[ci] == c && (C_ROW[ci] != r || C_COL[ci] != c))); then
                        case ${C_TYPE[ci]} in
                            0) printf '%b' "${DIM}${CRIT}·${RST}  " ;;
                            1) printf '%b' "${DIM}${HUDB}·${RST}  " ;;
                            2) printf '%b' "${DIM}${WARN}·${RST}  " ;;
                        esac
                        found=1; break
                    fi
                done
            fi

            if ((found == 0)); then
                if ((r == GRID_CY || c == GRID_CX)); then
                    if ((in_sweep)); then
                        printf '%b' "${BOLD}${HUDB}+${RST}  "
                    else
                        printf '%b' "${DIM}${HUD}·${RST}  "
                    fi
                else
                    local dsq=$((dy * dy * 4 + dx * dx))
                    local outer=$((GRID_CY * GRID_CY * 4))
                    local inner=$((outer / 4))
                    local tol=$((GRID_CY * 2))
                    if ((dsq > outer - tol && dsq < outer + tol)); then
                        if ((in_sweep)); then
                            printf '%b' "${BOLD}${HUDB}+${RST}  "
                        else
                            printf '%b' "${DIM}${HUD}·${RST}  "
                        fi
                    elif ((dsq > inner - tol && dsq < inner + tol)); then
                        if ((in_sweep)); then
                            printf '%b' "${BOLD}${HUDB}+${RST}  "
                        else
                            printf '%b' "${DIM}${HUD}·${RST}  "
                        fi
                    else
                        if ((in_sweep)); then
                            printf '%b' "${HUDB}·${RST}  "
                        else
                            printf '   '
                        fi
                    fi
                fi
            fi
        done

        # Pad and close — jump to right border column
        goto $((top + 1 + r)) $right_col
        printf '%b' "${DIM}${HUD}│${RST}"
    done

    # Bottom border
    goto $((top + GRID_ROWS + 1)) $left
    printf '%b' "${DIM}${HUD}└"
    for ((i = 1; i < width - 1; i++)); do printf '─'; done
    printf '%b' "┘${RST}"
}

draw_gauges() {
    local top=$TACT_TOP left=$RIGHT_X
    local width=$((COLS - left))
    local right_col=$((left + width - 1))
    local bar_w=$((width - 20))
    ((bar_w > 20)) && bar_w=20
    ((bar_w < 8)) && bar_w=8

    # Helper: clear from current cursor to right border, then draw │
    _gborder() {
        goto "$1" $right_col
        printf '%b' "${DIM}${HUD}│${RST}"
    }

    goto $top $left
    printf '%b' "${DIM}${HUD}┌─ SYSTEMS "
    # Visible prefix: ┌─ SYSTEMS  = 11 chars
    for ((i = 11; i < width - 1; i++)); do printf '─'; done
    printf '%b' "┐${RST}"

    for ((g = 0; g < NUM_GAUGES; g++)); do
        local val=${G_VAL[$g]} max=${G_MAX[$g]}
        local pct=$((val * 100 / max))
        local filled=$((pct * bar_w / 100))

        local col="${HUDB}"
        if ((g == 0)); then
            ((val > 450)) && col="${WARN}"; ((val > 550)) && col="${BOLD}${CRIT}"
        elif ((g == 1)); then
            ((pct > 60)) && col="${WARN}"; ((pct > 80)) && col="${BOLD}${CRIT}"
        else
            ((pct < 40)) && col="${WARN}"; ((pct < 20)) && col="${BOLD}${CRIT}"
        fi

        local r=$((top + 1 + g))
        goto $r $left
        printf '%b' "${DIM}${HUD}│${RST} ${DIM}${HUD}${G_NAME[$g]}${RST}"

        printf '%b' "${col}"
        for ((b = 0; b < bar_w; b++)); do
            if ((b < filled)); then printf '█'; else printf '%b' "${DIM}░${RST}${col}"; fi
        done

        local display_val=$pct
        ((g == 0)) && display_val=$val

        printf '%b' " $(printf '%3d' $display_val)${G_UNIT[$g]}${RST}"

        # Pad remaining space with blanks then border
        # Content width so far: 2(│ ) + 8(name) + bar_w + 5( NNN%) = 15 + bar_w
        local used=$((15 + bar_w))
        local pad=$((width - used - 1))
        ((pad > 0)) && printf "%*s" "$pad" ""
        _gborder $r
    done

    # Blank separator
    local row=$((top + NUM_GAUGES + 1))
    goto $row $left
    printf '%b' "${DIM}${HUD}│${RST}"
    _gborder $row

    # Contact list header
    row=$((row + 1))
    goto $row $left
    # Count hostiles
    local hostile_count=0
    for ((ci = 0; ci < NUM_CONTACTS; ci++)); do
        ((C_TYPE[ci] == 0)) && hostile_count=$((hostile_count + 1))
    done
    local threat_col="${HUDB}"
    ((hostile_count >= 3)) && threat_col="${WARN}"
    ((hostile_count >= 5)) && threat_col="${BOLD}${CRIT}"

    printf '%b' "${DIM}${HUD}│${RST} ${BOLD}${HUDB}CONTACTS ${RST}${threat_col}${NUM_CONTACTS}${RST}${DIM}/${hostile_count}H${RST}"
    # Fill with ─ to border
    # Visible: │ CONTACTS N/NH = 13 + len(num) + len(hostile), then space before fill
    local hdr_used=$((14 + ${#NUM_CONTACTS} + ${#hostile_count}))
    local hdr_pad=$((width - hdr_used - 1))
    printf '%b' " ${DIM}${HUD}"
    for ((i = 0; i < hdr_pad - 1; i++)); do printf '─'; done
    printf '%b' "${RST}"
    _gborder $row

    # Contact list
    local show=$NUM_CONTACTS
    ((show > 4)) && show=4
    for ((ci = 0; ci < show; ci++)); do
        row=$((row + 1))
        goto $row $left

        local tstr="" tcol=""
        case ${C_TYPE[ci]} in
            0) tstr="HOSTILE " tcol="${CRIT}" ;;
            1) tstr="FRIEND  " tcol="${HUDB}" ;;
            2) tstr="UNKNOWN " tcol="${WARN}" ;;
        esac

        local dy=$((C_ROW[ci] - GRID_CY))
        local dx=$((C_COL[ci] - GRID_CX))
        local dsq=$((dy * dy + dx * dx))
        local rkm=1
        ((dsq > 1)) && rkm=2; ((dsq > 4)) && rkm=3; ((dsq > 9)) && rkm=4
        ((dsq > 16)) && rkm=5; ((dsq > 25)) && rkm=6; ((dsq > 36)) && rkm=7

        # Content: │ ■ T-NN HOSTILE  Nkm  = about 23 chars
        printf '%b' "${DIM}${HUD}│${RST} ${tcol}■${RST} T-$(printf '%02d' $((ci+1))) ${tcol}${tstr}${RST}${DIM}${rkm}km${RST}"
        local c_used=23
        local c_pad=$((width - c_used - 1))
        ((c_pad > 0)) && printf "%*s" "$c_pad" ""
        _gborder $row
    done

    # Fill remaining rows to match tactical panel height
    local content_end=$((top + NUM_GAUGES + 3 + show))
    for ((r = content_end; r < TACT_BOTTOM; r++)); do
        goto $r $left
        printf '%b' "${DIM}${HUD}│${RST}"
        _gborder $r
    done

    # Bottom border — exact same width
    goto $TACT_BOTTOM $left
    printf '%b' "${DIM}${HUD}└"
    for ((i = 1; i < width - 1; i++)); do printf '─'; done
    printf '%b' "┘${RST}"
}

draw_waveform() {
    local top=$WAVE_TOP
    local width=$((COLS - 1))  # total inner width (col 1 to col COLS)
    local right_col=$COLS
    # Display width for waveform chars: total - borders(2) - label(12) - padding(2)
    local display_w=$((width - 16))
    ((display_w > WAVE_WIDTH)) && display_w=$WAVE_WIDTH

    # Compute signal strength (average of last 10 samples)
    local sig_sum=0
    for ((i = 0; i < 10; i++)); do
        local si=$(( (WAVE_HEAD - 1 - i + WAVE_WIDTH) % WAVE_WIDTH ))
        sig_sum=$((sig_sum + WAVE[si]))
    done
    local sig_pct=$((sig_sum * 100 / 70))
    ((sig_pct > 99)) && sig_pct=99

    # Compute BPM from heartbeat (count peaks in buffer)
    local bpm=$((68 + RANDOM % 8))

    # Top border
    goto $top 1
    printf '%b' "${DIM}${HUD}┌─ SIGNAL "
    for ((i = 10; i < width; i++)); do printf '─'; done
    printf '%b' "┐${RST}"

    # Signal waveform row
    goto $((top + 1)) 1
    printf '%b' "${DIM}${HUD}│${RST} "
    for ((i = 0; i < display_w; i++)); do
        local idx=$(( (WAVE_HEAD + i) % WAVE_WIDTH ))
        local v=${WAVE[$idx]}
        if ((v >= 6)); then printf '%b' "${BOLD}${HUDB}${WC[$v]}"
        elif ((v >= 4)); then printf '%b' "${HUDB}${WC[$v]}"
        elif ((v >= 2)); then printf '%b' "${HUD}${WC[$v]}"
        else printf '%b' "${DIM}${HUD}${WC[$v]}"; fi
    done
    printf '%b' "${RST}"
    goto $((top + 1)) $((right_col - 12))
    printf '%b' "${DIM} $(printf '%2d' $sig_pct)%% COMMS${DIM}${HUD}│${RST}"

    # Heartbeat row
    goto $((top + 2)) 1
    printf '%b' "${DIM}${HUD}│${RST} "
    for ((i = 0; i < display_w; i++)); do
        local idx=$(( (WAVE_HEAD + i) % WAVE_WIDTH ))
        local v=${HEART[$idx]}
        if ((v >= 6)); then printf '%b' "${BOLD}${CRIT}${WC[$v]}"
        elif ((v >= 4)); then printf '%b' "${CRIT}${WC[$v]}"
        elif ((v >= 2)); then printf '%b' "${WARN}${WC[$v]}"
        else printf '%b' "${DIM}${HUD}${WC[$v]}"; fi
    done
    printf '%b' "${RST}"
    goto $((top + 2)) $((right_col - 12))
    local bpm_col="${HUDB}"
    ((bpm > 72)) && bpm_col="${WARN}"
    printf '%b' "${DIM} ${bpm_col}${bpm}${RST}${DIM}bpm NEURO${DIM}${HUD}│${RST}"

    # Bottom border
    goto $((top + 3)) 1
    printf '%b' "${DIM}${HUD}└"
    for ((i = 1; i < width; i++)); do printf '─'; done
    printf '%b' "┘${RST}"
}

draw_compass() {
    local top=$COMP_TOP
    # Build triple compass strip for wrapping
    local one_rev="  N ──── NE ──── E ──── SE ──── S ──── SW ──── W ──── NW ──── "
    local strip="${one_rev}${one_rev}${one_rev}"
    local rev_len=64
    local pos=$((BEARING * rev_len / 360))
    local window=$((COLS - 8))
    local start=$((rev_len + pos - window / 2))

    goto $top 1
    printf '%b' " ${DIM}${HUD}${strip:$start:$window}${RST}"

    # Center pointer + hostile direction markers
    goto $((top + 1)) 1
    # Clear the line first
    printf "%*s" "$COLS" ""
    goto $((top + 1)) 1
    local center=$((window / 2 + 1))
    printf "%*s" "$center" ""
    printf '%b' "${BOLD}${HUDB}▲${RST}"

    # Show hostile direction markers on the pointer line
    for ((ci = 0; ci < NUM_CONTACTS; ci++)); do
        if ((C_TYPE[ci] == 0)); then
            # Compute rough bearing of contact relative to mech bearing
            local dx=$((C_COL[ci] - GRID_CX))
            local dy=$((GRID_CY - C_ROW[ci]))  # inverted Y
            # Map grid offset to rough compass offset on the strip
            local contact_offset=$((dx * 4))  # scale grid cells to strip chars
            local marker_pos=$((center + contact_offset))
            if ((marker_pos > 2 && marker_pos < window - 1)); then
                goto $((top + 1)) $((marker_pos + 1))
                if ((FRAME % 4 < 2)); then
                    printf '%b' "${BOLD}${CRIT}▼${RST}"
                else
                    printf '%b' "${CRIT}▼${RST}"
                fi
            fi
        fi
    done

    # Bearing + speed readout
    goto $top $((COLS - 18))
    printf '%b' "${DIM}BRG:${RST}${HUDB}$(printf '%03d' $BEARING)°${RST} ${DIM}SPD:${RST}${HUDB}$(printf '%3d' $SPEED)${RST}${DIM}kph${RST}"
}

draw_status() {
    local top=$STAT_TOP

    goto $top 1
    printf '%b' "${DIM}${HUD}"
    for ((i = 0; i < COLS; i++)); do printf '═'; done

    goto $top 2

    local rv=${G_VAL[0]} hp=$((G_VAL[1]*100/G_MAX[1])) ap=$((G_VAL[2]*100/G_MAX[2])) mp=$((G_VAL[5]*100/G_MAX[5]))
    local rc="${HUDB}" hc="${HUDB}" ac="${HUDB}" mc="${HUDB}"
    ((rv > 450)) && rc="${WARN}"; ((rv > 550)) && rc="${BOLD}${CRIT}"
    ((hp > 60)) && hc="${WARN}"; ((hp > 80)) && hc="${BOLD}${CRIT}"
    ((ap < 40)) && ac="${WARN}"; ((ap < 20)) && ac="${BOLD}${CRIT}"
    ((mp < 40)) && mc="${WARN}"; ((mp < 20)) && mc="${BOLD}${CRIT}"

    printf '%b' "${RST} ${DIM}REACTOR:${RST}${rc}$(printf '%3d' $rv)°C${RST}"
    printf '%b' " ${DIM}│${RST} ${DIM}HEAT:${RST}${hc}$(printf '%3d' $hp)%%${RST}"
    printf '%b' " ${DIM}│${RST} ${DIM}ARMOR:${RST}${ac}$(printf '%3d' $ap)%%${RST}"
    printf '%b' " ${DIM}│${RST} ${DIM}AMMO:${RST}${mc}$(printf '%3d' $mp)%%${RST}"
    printf '%b' " ${DIM}│${RST} ${DIM}TGT:${RST}${HUDB}${NUM_CONTACTS}${RST}"

    # Event bar
    if ((STAT_TOP + 1 <= ROWS)); then
        goto $((top + 1)) 1
        printf "%*s" "$COLS" ""
        if [[ -n "$EVENT_MSG" ]]; then
            goto $((top + 1)) 2
            if ((FLASH_TTL > 0)); then
                # Critical events flash red/bright
                if ((EVENT_TTL % 3 == 0)); then
                    printf '%b' " ${BOLD}${CRIT}▶▶ ${EVENT_MSG}${RST}"
                else
                    printf '%b' " ${WARN}▶▶ ${EVENT_MSG}${RST}"
                fi
            elif [[ "$EVENT_MSG" == *":"* ]]; then
                # Comms chatter (contains : from CALLSIGN:)
                printf '%b' " ${DIM}${HUD}▶ ${RST}${HUD}${EVENT_MSG}${RST}"
            else
                # Regular events
                if ((EVENT_TTL % 4 < 2)); then
                    printf '%b' " ${BOLD}${HUDB}▶ ${EVENT_MSG}${RST}"
                else
                    printf '%b' " ${WARN}▶ ${EVENT_MSG}${RST}"
                fi
            fi
        fi
    fi
}

# ══════════════════════════════════════════
#  BOOT SEQUENCE
# ══════════════════════════════════════════

boot() {
    local cx=$((COLS / 2))
    local cy=$((ROWS / 2 - 6))

    # Static noise burst
    local hex_chars="0123456789ABCDEF"
    for ((pass = 0; pass < 3; pass++)); do
        for ((row = 1; row <= ROWS; row++)); do
            goto $row 1
            local line=""
            for ((col = 0; col < COLS; col++)); do
                if ((RANDOM % 3 == 0)); then
                    line+="${hex_chars:$((RANDOM % 16)):1}"
                else
                    line+=" "
                fi
            done
            printf '%b' "${DIM}${HUD}${line}${RST}"
        done
        sleep 0.06
    done
    clear
    sleep 0.3

    # Power-on flash
    for ((row = 1; row <= ROWS; row++)); do
        goto $row 1
        printf '%b' "${BOLD}${HUDB}"
        for ((col = 0; col < COLS; col++)); do printf '█'; done
        printf '%b' "${RST}"
    done
    sleep 0.08
    clear
    sleep 0.4

    # Mech designation
    goto $((cy - 2)) $((cx - 20))
    printf '%b' "${DIM}${HUD}╔══════════════════════════════════════╗${RST}"
    goto $((cy - 1)) $((cx - 20))
    printf '%b' "${DIM}${HUD}║${RST}${BOLD}${HUDB}  BATTLE MECH OPERATING SYSTEM v4.7  ${RST}${DIM}${HUD}║${RST}"
    goto $((cy)) $((cx - 20))
    printf '%b' "${DIM}${HUD}╚══════════════════════════════════════╝${RST}"
    sleep 0.8

    # System checks with animated dots
    local systems=("FUSION REACTOR" "SENSOR ARRAY  " "WEAPONS BUS   " "NEURAL LINK   " "TACTICAL NET  " "GYRO STABILIZE" "LIFE SUPPORT  ")
    local results=("ONLINE" "ONLINE" "ONLINE" "SYNCED" "LINKED" "LOCKED" "ACTIVE")

    for ((s = 0; s < ${#systems[@]}; s++)); do
        local row=$((cy + 2 + s))
        goto $row $((cx - 16))
        printf '%b' "${DIM}${HUD}${systems[$s]} ${RST}"

        # Animated dots
        for ((d = 0; d < 4; d++)); do
            printf '%b' "${DIM}${HUD}.${RST}"
            sleep 0.08
        done

        # Brief random hex burst
        printf '%b' " ${DIM}${HUD}"
        for ((h = 0; h < 6; h++)); do
            printf '%b' "${hex_chars:$((RANDOM % 16)):1}"
        done
        printf '%b' "${RST}"
        sleep 0.15

        # Clear hex and show result
        goto $row $((cx + 5))
        printf '%b' "       "
        goto $row $((cx + 5))
        if ((s == 2)); then
            # Weapons bus gets a brief warning then resolves
            printf '%b' "${WARN}CHECK${RST}"
            sleep 0.3
            goto $row $((cx + 5))
        fi
        printf '%b' "${BOLD}${HUDB} ${results[$s]}${RST}"
        sleep 0.12
    done

    sleep 0.4

    # Loading bar with percentage
    local bw=30
    goto $((cy + 10)) $((cx - 20))
    printf '%b' "${DIM}${HUD}INITIALIZING HEADS-UP DISPLAY${RST}"
    for ((i = 0; i <= bw; i++)); do
        local pct=$((i * 100 / bw))
        goto $((cy + 11)) $((cx - bw / 2 - 4))
        printf '%b' "${HUDB}["
        for ((j = 0; j < bw; j++)); do
            if ((j <= i)); then printf '█'; else printf '%b' "${DIM}░${RST}${HUDB}"; fi
        done
        printf '%b' "] $(printf '%3d' $pct)%%${RST}"
        sleep 0.03
    done

    sleep 0.3

    # Final ready message with callsign
    goto $((cy + 13)) $((cx - 16))
    printf '%b' "${BOLD}${HUDB}» ${CALLSIGN} « ALL SYSTEMS NOMINAL${RST}"
    goto $((cy + 14)) $((cx - 16))
    printf '%b' "${DIM}${HUD}PILOT: ${PILOT}  //  ${MECH}${RST}"
    sleep 1.0

    # Fade out with brief static
    for ((pass = 0; pass < 2; pass++)); do
        for ((row = 1; row <= ROWS; row += 2)); do
            goto $row 1
            for ((col = 0; col < COLS; col++)); do
                if ((RANDOM % 4 == 0)); then
                    printf '%b' "${DIM}${HUD}${hex_chars:$((RANDOM % 16)):1}${RST}"
                else
                    printf ' '
                fi
            done
        done
        sleep 0.05
    done

    clear
}

boot

# ══════════════════════════════════════════
#  MAIN LOOP
# ══════════════════════════════════════════

while true; do
    update_contacts
    update_gauges
    update_waveform
    update_bearing
    update_sweep
    update_events

    draw_title
    draw_tactical
    draw_gauges
    draw_waveform
    draw_compass
    draw_status

    FRAME=$((FRAME + 1))
    sleep 0.18
done
