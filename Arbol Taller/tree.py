"""Attack tree data structures and risk calculations for HackTree.

The tree is built and processed entirely in Python. The frontend only
renders what the API returns.
"""
from __future__ import annotations

import unicodedata
from collections import deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Iterator, List, Optional


class Gate(str, Enum):
    """Logical relationship between the children of a node."""

    OR = "OR"    # Any child is enough to achieve the parent goal.
    AND = "AND"  # Every child is required to achieve the parent goal.


def classify_risk(probability: float) -> str:
    """Map a probability to a risk level key."""
    if probability < 0.2:
        return "low"
    if probability < 0.5:
        return "medium"
    return "high"


def normalize_text(text: str) -> str:
    """Lowercase text and strip accents so searches are accent-insensitive."""
    decomposed = unicodedata.normalize("NFD", text.lower())
    return "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")


@dataclass
class Mitigation:
    """A defensive measure that lowers the probability of a leaf attack."""

    id: str
    name: str
    description: str
    effectiveness: float  # Fraction of the probability removed (0.0 - 1.0).
    active: bool = False

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "effectiveness": self.effectiveness,
            "active": self.active,
        }


class Node:
    """A node of the attack tree."""

    def __init__(
        self,
        node_id: str,
        label: str,
        description: str = "",
        gate: Gate = Gate.OR,
        base_probability: float = 0.0,
        impact: int = 1,
    ) -> None:
        self.id = node_id
        self.label = label
        self.description = description
        self.gate = gate
        self.base_probability = base_probability  # Only used by leaves.
        self._impact = impact                      # Only used by leaves.
        self.children: List[Node] = []
        self.parent: Optional[Node] = None
        self.mitigations: List[Mitigation] = []

    # ----- Structure -------------------------------------------------------
    def add_child(self, child: "Node") -> "Node":
        child.parent = self
        self.children.append(child)
        return child

    def add_mitigation(self, mitigation: Mitigation) -> Mitigation:
        self.mitigations.append(mitigation)
        return mitigation

    @property
    def is_leaf(self) -> bool:
        return not self.children

    def depth(self) -> int:
        """Number of edges between this node and the root."""
        depth, node = 0, self
        while node.parent is not None:
            depth += 1
            node = node.parent
        return depth

    def height(self) -> int:
        """Number of edges on the longest path down to a leaf."""
        if self.is_leaf:
            return 0
        return 1 + max(child.height() for child in self.children)

    def path_from_root(self) -> List["Node"]:
        path: List[Node] = []
        node: Optional[Node] = self
        while node is not None:
            path.append(node)
            node = node.parent
        return list(reversed(path))

    # ----- Traversals ------------------------------------------------------
    def dfs(self) -> Iterator["Node"]:
        """Depth-first, pre-order traversal."""
        yield self
        for child in self.children:
            yield from child.dfs()

    def bfs(self) -> Iterator["Node"]:
        """Breadth-first (level order) traversal."""
        queue = deque([self])
        while queue:
            node = queue.popleft()
            yield node
            queue.extend(node.children)

    def find(self, node_id: str) -> Optional["Node"]:
        for node in self.dfs():
            if node.id == node_id:
                return node
        return None

    # ----- Risk model ------------------------------------------------------
    def impact(self) -> int:
        """Leaves store their impact; inner nodes inherit the worst child."""
        if self.is_leaf:
            return self._impact
        return max(child.impact() for child in self.children)

    def probability(self, use_mitigations: bool = True) -> float:
        """Probability that this node's goal is achieved by an attacker.

        Leaf: base probability reduced by every active mitigation.
        OR gate:  1 - product(1 - p_child)
        AND gate: product(p_child)
        """
        if self.is_leaf:
            value = self.base_probability
            if use_mitigations:
                for mitigation in self.mitigations:
                    if mitigation.active:
                        value *= 1 - mitigation.effectiveness
            return value

        child_values = [c.probability(use_mitigations) for c in self.children]
        result = 1.0
        if self.gate == Gate.AND:
            for value in child_values:
                result *= value
            return result
        for value in child_values:
            result *= 1 - value
        return 1 - result

    def risk(self, use_mitigations: bool = True) -> float:
        """Risk score from 0 to 10: probability multiplied by impact."""
        return self.probability(use_mitigations) * self.impact()

    # ----- Serialization ---------------------------------------------------
    def to_dict(self) -> dict:
        current = self.probability(True)
        return {
            "id": self.id,
            "label": self.label,
            "description": self.description,
            "gate": self.gate.value if not self.is_leaf else None,
            "is_leaf": self.is_leaf,
            "depth": self.depth(),
            "impact": self.impact(),
            "probability": round(current, 4),
            "baseline_probability": round(self.probability(False), 4),
            "risk": round(self.risk(True), 2),
            "risk_level": classify_risk(current),
            "mitigations": [m.to_dict() for m in self.mitigations],
            "children": [child.to_dict() for child in self.children],
        }


class AttackTree:
    """Wrapper that owns the root node and a lookup index."""

    def __init__(self, root: Node) -> None:
        self.root = root
        self._index: Dict[str, Node] = {}
        self._mitigations: Dict[str, Mitigation] = {}
        for node in root.dfs():
            self._index[node.id] = node
            for mitigation in node.mitigations:
                self._mitigations[mitigation.id] = mitigation

    def get_node(self, node_id: str) -> Optional[Node]:
        return self._index.get(node_id)

    def get_mitigation(self, mitigation_id: str) -> Optional[Mitigation]:
        return self._mitigations.get(mitigation_id)

    def toggle_mitigation(self, mitigation_id: str) -> Optional[Mitigation]:
        mitigation = self._mitigations.get(mitigation_id)
        if mitigation is not None:
            mitigation.active = not mitigation.active
        return mitigation

    def reset(self) -> None:
        for mitigation in self._mitigations.values():
            mitigation.active = False

    def search(self, query: str) -> List[Node]:
        needle = normalize_text(query.strip())
        if not needle:
            return []
        return [
            node
            for node in self.root.dfs()
            if needle in normalize_text(node.label)
            or needle in normalize_text(node.description)
        ]

    def stats(self) -> dict:
        nodes = list(self.root.dfs())
        leaves = [n for n in nodes if n.is_leaf]
        top = sorted(leaves, key=lambda n: n.risk(True), reverse=True)[:3]
        active = sum(1 for m in self._mitigations.values() if m.active)
        return {
            "total_nodes": len(nodes),
            "leaf_nodes": len(leaves),
            "height": self.root.height(),
            "baseline_probability": round(self.root.probability(False), 4),
            "current_probability": round(self.root.probability(True), 4),
            "active_mitigations": active,
            "total_mitigations": len(self._mitigations),
            "top_threats": [
                {"id": n.id, "label": n.label, "risk": round(n.risk(True), 2)}
                for n in top
            ],
        }


def create_default_tree() -> AttackTree:
    """Build the educational 'compromised corporate account' scenario."""
    root = Node(
        "root",
        "¿Cómo podría comprometerse una cuenta corporativa?",
        "Objetivo principal del atacante en este escenario simulado.",
        Gate.OR,
    )

    # --- Weak passwords ---------------------------------------------------
    passwords = root.add_child(Node(
        "weak-passwords", "Políticas de contraseñas débiles",
        "Las contraseñas son fáciles de adivinar o de reutilizar.", Gate.OR))
    policy = passwords.add_child(Node(
        "permissive-policy", "Política de contraseñas permisiva",
        "Se aceptan contraseñas cortas y comunes.",
        base_probability=0.25, impact=6))
    policy.add_mitigation(Mitigation(
        "min-length", "Exigir 14 caracteres como mínimo",
        "Una política de longitud mínima elimina la mayoría de contraseñas triviales.", 0.6))
    reuse = passwords.add_child(Node(
        "password-reuse", "Reutilización de contraseñas entre servicios",
        "Una filtración externa podría exponer credenciales válidas aquí.",
        base_probability=0.30, impact=7))
    reuse.add_mitigation(Mitigation(
        "password-manager", "Proveer un gestor de contraseñas corporativo",
        "Facilita usar una contraseña única y larga por servicio.", 0.6))
    lockout = passwords.add_child(Node(
        "no-lockout", "Sin bloqueo tras intentos fallidos",
        "El sistema permite intentos ilimitados de inicio de sesión.",
        base_probability=0.15, impact=6))
    lockout.add_mitigation(Mitigation(
        "progressive-lockout", "Bloqueo progresivo de cuentas",
        "Cada intento fallido aumenta el tiempo de espera.", 0.7))

    # --- Phishing ---------------------------------------------------------
    phishing = root.add_child(Node(
        "phishing", "Phishing e ingeniería social",
        "Se engaña a una persona para obtener acceso.", Gate.OR))
    email = phishing.add_child(Node(
        "phishing-email", "Correo fraudulento exitoso",
        "Requiere que el mensaje llegue y que la persona caiga en el engaño.", Gate.AND))
    untrained = email.add_child(Node(
        "untrained-staff", "Personal sin capacitación en seguridad",
        "Las personas no reconocen señales de un correo sospechoso.",
        base_probability=0.50, impact=7))
    untrained.add_mitigation(Mitigation(
        "awareness-training", "Capacitación y simulacros periódicos",
        "Entrena a las personas a reportar mensajes sospechosos.", 0.6))
    filter_ = email.add_child(Node(
        "weak-mail-filter", "Filtro de correo deficiente",
        "Los mensajes sospechosos llegan a la bandeja de entrada.",
        base_probability=0.30, impact=7))
    filter_.add_mitigation(Mitigation(
        "mail-filtering", "Filtrado avanzado de correo y enlaces",
        "Bloquea remitentes falsos y enlaces peligrosos.", 0.7))
    phone = phishing.add_child(Node(
        "phone-impersonation", "Suplantación telefónica de soporte técnico",
        "Alguien se hace pasar por soporte para pedir acceso.",
        base_probability=0.10, impact=6))
    phone.add_mitigation(Mitigation(
        "callback-policy", "Verificar identidad por un canal oficial",
        "Soporte nunca pide credenciales; se devuelve la llamada a un número oficial.", 0.8))

    # --- Missing MFA ------------------------------------------------------
    mfa = root.add_child(Node(
        "missing-mfa", "Falta de autenticación multifactor",
        "Una credencial robada basta si no hay un segundo factor.", Gate.AND))
    stolen = mfa.add_child(Node(
        "stolen-credential", "Credencial obtenida por otro medio",
        "Contraseña filtrada, adivinada o capturada.",
        base_probability=0.40, impact=8))
    stolen.add_mitigation(Mitigation(
        "breach-monitoring", "Monitorear filtraciones de credenciales",
        "Forzar el cambio de contraseña cuando aparece en una filtración.", 0.4))
    no_mfa = mfa.add_child(Node(
        "mfa-disabled", "MFA no habilitado en la cuenta",
        "La cuenta solo está protegida por contraseña.",
        base_probability=0.60, impact=8))
    no_mfa.add_mitigation(Mitigation(
        "mfa-enforcement", "Exigir MFA en todas las cuentas",
        "Un segundo factor bloquea el acceso aunque la contraseña se filtre.", 0.9))

    # --- Excessive permissions --------------------------------------------
    permissions = root.add_child(Node(
        "excessive-permissions", "Permisos excesivos en las cuentas",
        "Una cuenta comprometida tiene más alcance del necesario.", Gate.OR))
    admin = permissions.add_child(Node(
        "unneeded-admin", "Privilegios de administrador innecesarios",
        "Personas con rol administrativo sin necesitarlo.",
        base_probability=0.20, impact=9))
    admin.add_mitigation(Mitigation(
        "least-privilege", "Aplicar el principio de mínimo privilegio",
        "Cada cuenta recibe solo los permisos que su rol requiere.", 0.6))
    review = permissions.add_child(Node(
        "no-access-review", "Sin revisión periódica de accesos",
        "Los permisos acumulados nunca se auditan.",
        base_probability=0.20, impact=7))
    review.add_mitigation(Mitigation(
        "access-reviews", "Revisiones trimestrales de accesos",
        "Se retiran permisos que ya no se justifican.", 0.5))
    orphan = permissions.add_child(Node(
        "orphan-accounts", "Cuentas huérfanas de exempleados",
        "Cuentas activas que nadie usa ni vigila.",
        base_probability=0.15, impact=7))
    orphan.add_mitigation(Mitigation(
        "offboarding", "Proceso automático de baja de cuentas",
        "Las cuentas se desactivan el mismo día de la salida.", 0.9))

    # --- Inadequate monitoring --------------------------------------------
    monitoring = root.add_child(Node(
        "weak-monitoring", "Monitoreo de seguridad inadecuado",
        "Un acceso indebido pasa desapercibido el tiempo suficiente para hacer daño.", Gate.OR))
    alerts = monitoring.add_child(Node(
        "no-login-alerts", "Sin alertas de inicios de sesión anómalos",
        "Nadie nota accesos desde ubicaciones o horarios inusuales.",
        base_probability=0.30, impact=6))
    alerts.add_mitigation(Mitigation(
        "anomaly-alerts", "Alertas de inicio de sesión inusual",
        "Notifica al equipo de seguridad en tiempo real.", 0.7))
    logs = monitoring.add_child(Node(
        "scattered-logs", "Registros dispersos y sin centralizar",
        "Reconstruir un incidente toma días.",
        base_probability=0.25, impact=5))
    logs.add_mitigation(Mitigation(
        "central-logging", "Centralizar registros en un único sistema",
        "Permite correlacionar eventos y detectar patrones.", 0.6))

    return AttackTree(root)
